import datetime
import logging
from typing import Optional

from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.db.models import QuerySet
from django.forms import inlineformset_factory, modelform_factory
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils.encoding import force_str
from django.utils.functional import cached_property
from django.utils.translation import gettext as _
from django.views import View
from crispy_forms.layout import Layout

from core.models import Template, Workflow, Approval

logger = logging.getLogger(__name__)


class BaseViewMixin(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Optimized base mixin with safe caching for static metadata,
    live queries for approval-related data, and reduced memory usage.
    """

    actions = []
    template_name = None
    DEBUG = settings.DEBUG
    ALLOWED_APPS = {'employee', 'leave', 'payroll'}

    # ========================
    # Cached Static Metadata
    # ========================

    @cached_property
    def model_class(self):
        """Return the model class from URL kwargs."""
        return apps.get_model(self.kwargs['app'], model_name=self.kwargs['model'])

    @cached_property
    def model_fields(self):
        """Dict of field_name → Field instance for the model."""
        return {f.name: f for f in self.model_class._meta.fields}

    @cached_property
    def content_type(self):
        """Cached content type for the model."""
        if not self._model_allowed():
            return None
        return ContentType.objects.get_for_model(self.model_class, for_concrete_model=False)

    @cached_property
    def documents(self):
        """Fetch only necessary fields to reduce memory usage."""
        return Template.objects.only('id', 'name', 'content_type').filter(
            content_type=self.content_type
        )

    @cached_property
    def sub_organization(self):
        """Cache DB hit for sub_organization lookup."""
        SubOrganization = apps.get_model('core', 'suborganization')
        sub_name = self.get_subdomain()
        return SubOrganization.objects.filter(name__iexact=sub_name.lower()).first() if sub_name else None

    # ========================
    # Object / Field Checks
    # ========================

    def _get_object(self):
        """Override in subclasses to return a single instance."""
        return None

    def model_has_field(self, model_class, field_name):
        """Efficient field existence check using cached set."""
        return field_name in {f.name for f in model_class._meta.fields}

    # ========================
    # Permissions & Templates
    # ========================

    def get_actions(self):
        return self.actions

    def get_permission_required(self):
        if not self.request.user.is_authenticated:
            return []
        app = self.kwargs['app']
        model = self.kwargs['model']
        return [f"{app}.{action}_{model}" for action in self.get_actions()]

    def handle_no_permission(self):
        if self.get_permission_required():
            messages.warning(self.request, _("You don't have permission to perform this action."))
            logger.warning("Permission denied: %s", self.request.user)
        return HttpResponseRedirect(self.request.META.get('HTTP_REFERER', reverse_lazy('login')))

    def get_template_name(self):
        return getattr(self.model_class, 'list_template', self.template_name)

    # ========================
    # QuerySet Filtering
    # ========================

    def get_queryset(self, model_class=None):
        model = model_class or self.model_class
        user = self.request.user
        qs = model.objects.all()

        if hasattr(qs, 'for_user'):
            qs = qs.for_user(user=user)

        rls = user.get_user_rls(app=model._meta.app_label, model=model._meta.model_name)
        suborg = getattr(self.request, 'suborganization', None)
        if suborg and self.model_has_field(model, 'sub_organization'):
            qs = qs.filter(sub_organization=suborg)

        return qs.filter(**rls)

    # ========================
    # Document Support
    # ========================

    def is_approved(self):
        obj = self._get_object()
        return not hasattr(obj, 'status') or obj.status == "APPROVED"

    # ========================
    # Logging Utilities
    # ========================

    def get_subdomain(self):
        host = self.request.get_host().split(':')[0]
        parts = host.split('.')
        return parts[0] if len(parts) >= 3 else None

    def logs(self):
        """Fetch only necessary fields for log display."""
        return LogEntry.objects.filter(
            content_type=self.content_type,
            object_id=self.kwargs.get('pk')
        ).only('change_message', 'action_time')

    def generate_change_message(self, old_instance, new_instance):
        excludes = {"created_at", "updated_at", "id", "pk"}
        changes = []
        for field in (f for f in old_instance._meta.fields if f.name not in excludes):
            old_val, new_val = getattr(old_instance, field.name, None), getattr(new_instance, field.name, None)
            if old_val != new_val:
                verbose = field.verbose_name
                changes.append(_("Field '%(field)s' changed from '%(old)s' to '%(new)s'.") % {
                    'field': verbose, 'old': old_val, 'new': new_val
                })
        return "\n".join(changes) if changes else _("No change found")

    def log(self, model, form, action, change_message):
        if change_message:
            return LogEntry.objects.log_action(
                user_id=self.request.user.id,
                content_type_id=ContentType.objects.get_for_model(model).id,
                object_id=form.instance.pk,
                object_repr=force_str(form.instance),
                action_flag=action,
                change_message=change_message
            )

    # ========================
    # Forms & Inline Support
    # ========================

    def get_form_fields(self, model=None):
        model = model or self.model_class
        layout = getattr(model, 'layout', Layout())
        return [field.name for field in layout.get_field_names()]

    def get_inline_form_fields(self, model=None):
        model = model or self.model_class
        return [f.name for f in model._meta.fields if getattr(f, 'inline', False)]

    def filter_form(self, form):
        """Mark protected fields readonly in a single pass."""
        if isinstance(form, type):
            form = form()
        model = form._meta.model
        perms = self.request.user.get_user_field_permission(app=model._meta.app_label, model=model._meta.model_name)
        protected = {k for k, v in perms.items() if v} | {'sub_organization', 'employee'}
        for field in protected & form.fields.keys():
            form.fields[field].widget.attrs.update({
                'readonly': True, 'class': 'bg-dark', 'style': 'pointer-events: none'
            })
        return form

    def inline_model_form(self, model):
        fields = self.get_inline_form_fields(model)
        base_form_class = modelform_factory(model, fields=fields)
        filtered_form = self.filter_form(base_form_class())
        widgets = {f: filtered_form.fields[f].widget for f in fields}
        return modelform_factory(model, fields=fields, widgets=widgets)

    def formsets(self, can_delete=True, extra=1):
        result = []
        for inline in getattr(self.model_class, 'inlines', tuple()):
            model = apps.get_model(*inline.split('.'))
            FormSet = inlineformset_factory(
                self.model_class, model,
                form=self.inline_model_form(model),
                fields=self.get_inline_form_fields(model),
                can_delete=can_delete, extra=extra
            )
            result.append(FormSet)
        return result

    # ========================
    # Workflow / Approval (Live Queries)
    # ========================

    def _model_allowed(self, model=None):
        model = model or self.model_class
        return model._meta.app_label in self.ALLOWED_APPS

    def approvals(self) -> QuerySet:
        """Always fetch fresh approvals."""
        obj = self._get_object()
        if not obj or not self._model_allowed(type(obj)):
            return Approval.objects.none()
        content_type = ContentType.objects.get_for_model(obj, for_concrete_model=False)
        return Approval.objects.filter(content_type=content_type, object_id=obj.pk).select_related('user')

    def approval(self) -> Optional[Approval]:
        """Always fetch fresh approval for the current user."""
        return self.approvals().filter(user=self.request.user).first()

    def user_can_approve(self) -> bool:
        approval = self.approval()
        return bool(approval and approval.status not in {'APPROVED', 'REJECTED'})

    def approval_users(self) -> QuerySet:
        """Always fetch fresh list of users who can approve."""
        if not self._model_allowed():
            return get_user_model().objects.none()
        return get_user_model().objects.filter(pk__in=self.approvals().values_list('user_id', flat=True))

    def get_workflow_users_for_model(self) -> QuerySet:
        if not self._model_allowed() or not self.content_type:
            return get_user_model().objects.none()

        obj = self._get_object()
        workflows = Workflow.objects.filter(content_type=self.content_type).prefetch_related('users')

        user_ids = set()
        for wf in workflows:
            try:
                # WARNING: eval remains unsafe unless replaced with a parser
                if eval(wf.condition, {"__builtins__": {}}, {"obj": obj, "self": self}):
                    user_ids.update(wf.users.values_list('pk', flat=True))
            except Exception as e:
                logger.warning("Workflow condition failed: %s — %s", wf.condition, e)

        return get_user_model().objects.filter(pk__in=user_ids)

    # ========================
    # Keywords for Search
    # ========================

    def get_custom_keyword_models(self):
        return []
