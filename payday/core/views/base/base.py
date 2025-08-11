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
    A single powerful base mixin that consolidates model loading, permission checks,
    queryset filtering, logging, workflow, document retrieval, form generation,
    and keyword generation. Designed for performance and extensibility.
    """

    actions = []
    template_name = None
    DEBUG = settings.DEBUG

    # ========================
    # Model Properties
    # ========================

    @property
    def model_class(self):
        """Return the model class from URL kwargs."""
        return apps.get_model(self.kwargs['app'], model_name=self.kwargs['model'])

    @cached_property
    def content_type(self):
        """Return the content type of the current model."""
        if not self._model_allowed():
            return None
        return ContentType.objects.get_for_model(self.model_class, for_concrete_model=False)

    def _get_object(self):
        """Override in subclasses to return a single instance."""
        return None

    def model_has_field(self, model_class, field_name):
        """Check if a model has a given field."""
        return field_name in [f.name for f in model_class._meta.fields]

    # ========================
    # Permissions & Templates
    # ========================

    def get_actions(self):
        """Return allowed actions (add/view/edit/delete)."""
        return self.actions

    def get_permission_required(self):
        """Generate permission strings based on model and actions."""
        if not self.request.user.is_authenticated:
            return []
        return [f"{self.kwargs['app']}.{action}_{self.kwargs['model']}" for action in self.get_actions()]

    def handle_no_permission(self):
        """Redirect with warning if permission denied."""
        if self.get_permission_required():
            messages.warning(self.request, _("You don't have permission to perform this action."))
            logger.warning(f"Permission denied: {self.request.user}")
        return HttpResponseRedirect(self.request.META.get('HTTP_REFERER', reverse_lazy('login')))

    def get_template_name(self):
        """Return custom template or fallback."""
        return getattr(self.model_class, 'list_template', self.template_name)

    # ========================
    # QuerySet Filtering
    # ========================

    def get_queryset(self, model_class=None):
        """Return filtered queryset based on user-level security."""
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

    def documents(self):
        """Return document templates associated with current model."""
        return Template.objects.filter(
            content_type__app_label=self.model_class._meta.app_label,
            content_type__model=self.model_class._meta.model_name
        )

    # ========================
    # Logging Utilities
    # ========================

    def get_subdomain(self):
        host = self.request.get_host().split(':')[0]  # Remove port if present
        domain_parts = host.split('.')

        # Example: sub.example.com → ['sub', 'example', 'com']
        if len(domain_parts) >= 3:
            return domain_parts[0]  # Assumes subdomain is the first part
        return None  # No subdomain present


    def sub_organization(self):
        SubOrganization = apps.get_model('core', 'suborganization')
        sub_organization = self.get_subdomain()
        return SubOrganization.objects.filter(
            name__iexact=sub_organization
        ).first()

    def logs(self):
        """Return audit logs for current object."""
        return LogEntry.objects.filter(
            content_type=self.content_type,
            object_id=self.kwargs.get('pk')
        ).values('change_message', 'action_time')

    def generate_change_message(self, old_instance, new_instance):
        """Return human-readable change log."""
        excludes = {"created_at", "updated_at", "id", "pk"}
        changes = []

        for field in [f.name for f in old_instance._meta.fields if f.name not in excludes]:
            old_val, new_val = getattr(old_instance, field, None), getattr(new_instance, field, None)
            if old_val != new_val:
                verbose = new_instance._meta.get_field(field).verbose_name
                changes.append(_(f"Field '{verbose}' changed from '{old_val}' to '{new_val}'."))

        return "\n".join(changes) if changes else "No change found"

    def log(self, model, form, action, change_message):
        """Create a log entry."""
        if not change_message:
            return
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
        """Get fields from model layout (Crispy Form)."""
        model = model or self.model_class
        layout = getattr(model, 'layout', Layout())
        return [field.name for field in layout.get_field_names()]

    def get_inline_form_fields(self, model=None):
        """Return fields marked as inline=True."""
        model = model or self.model_class
        return [f.name for f in model._meta.fields if getattr(f, 'inline', False)]

    def filter_form(self, form):
        """Apply field-level permission restrictions (readonly)."""
        if isinstance(form, type):
            form = form()

        model = form._meta.model
        perms = self.request.user.get_user_field_permission(app=model._meta.app_label, model=model._meta.model_name)
        protected = {k for k, v in perms.items() if v} | {'sub_organization', 'employee'}

        for field in protected:
            if field in form.fields:
                form.fields[field].widget.attrs.update({
                    'readonly': True,
                    'class': 'bg-dark',
                    'style': 'pointer-events: none'
                })
        return form

    def inline_model_form(self, model):
        """Return custom form class for an inline model."""
        fields = self.get_inline_form_fields(model)
        temp_form = modelform_factory(model, fields=fields)
        filtered = self.filter_form(temp_form())
        widgets = {f: filtered.fields[f].widget for f in filtered.fields}
        return modelform_factory(model, fields=fields, widgets=widgets)

    def formsets(self, can_delete=True, extra=1):
        """Return list of inline formsets for model."""
        formsets = []
        inlines = getattr(self.model_class, 'inlines', tuple())
        for inline in inlines:
            model = apps.get_model(*inline.split('.'))
            FormSet = inlineformset_factory(
                self.model_class, model,
                form=self.inline_model_form(model),
                fields=self.get_inline_form_fields(model),
                can_delete=can_delete, extra=extra
            )
            formsets.append(FormSet)
        return formsets

    # ========================
    # Workflow / Approval
    # ========================

    ALLOWED_APPS = {'employee', 'leave', 'payroll'}

    def _model_allowed(self, model=None):
        """Check if workflow is allowed for this model."""
        model = model or self.model_class
        return model._meta.app_label in self.ALLOWED_APPS

    @property
    def approvals(self) -> QuerySet:
        """Return all approvals for current object."""
        obj = self._get_object()
        if not obj or not self._model_allowed(type(obj)):
            return Approval.objects.none()
        content_type = ContentType.objects.get_for_model(obj, for_concrete_model=False)
        return Approval.objects.filter(content_type=content_type, object_id=obj.pk).select_related('user')

    @property
    def approval(self) -> Optional[Approval]:
        """Return current user's approval instance if it exists."""
        if not hasattr(self, 'request'):
            return None
        return self.approvals.filter(user=self.request.user).first()

    @property
    def user_can_approve(self) -> bool:
        """Check if user is allowed to approve."""
        obj = self._get_object()
        if not obj or self.request.user == getattr(obj, 'created_by', None):
            return False
        approval = self.approval
        return approval and approval.status not in {'APPROVED', 'REJECTED'}

    @property
    def approval_users(self) -> QuerySet:
        """Return users who can approve the object."""
        if not self._model_allowed():
            return get_user_model().objects.none()
        return get_user_model().objects.filter(pk__in=self.approvals.values_list('user_id', flat=True).distinct())

    def get_workflow_users_for_model(self) -> QuerySet:
        """Get users who match workflow conditions."""
        if not self._model_allowed() or not self.content_type:
            return get_user_model().objects.none()

        obj = self._get_object()
        workflows = Workflow.objects.filter(content_type=self.content_type).prefetch_related('users')

        user_ids = set()
        for wf in workflows:
            try:
                if eval(wf.condition, {"__builtins__": {}}, {"obj": obj, "self": self}):
                    user_ids.update(wf.users.values_list('pk', flat=True))
            except Exception as e:
                logger.warning(f"Workflow condition failed: {wf.condition} — {e}")

        return get_user_model().objects.filter(pk__in=user_ids).distinct()

    # ========================
    # Keywords for Search
    # ========================

    def get_custom_keyword_models(self):
        """Override to inject additional models for keyword support."""
        return []

    def keywords(self):
        """Return keyword definitions for search filters."""
        base = [
            {'name': _('vrai'), 'meta': 'boolean', 'value': 'True'},
            {'name': _('faux'), 'meta': 'boolean', 'value': 'False'},
            {'name': _('null'), 'meta': 'null', 'value': 'None'},
            {'name': _('vide'), 'meta': 'empty', 'value': ''},
            {'name': _('aujourdhui'), 'meta': 'date', 'value': str(datetime.date.today())},
            {'name': _('maintenant'), 'meta': 'datetime', 'value': str(datetime.datetime.now())}
        ]
        exclude = {'created_by', 'updated_by', 'created_at', 'updated_at'}

        for model in self.get_custom_keyword_models():
            for field in model._meta.fields:
                if field.name in exclude:
                    continue
                if not field.is_relation:
                    base.append({
                        'name': f"{model._meta.model_name}.{field.verbose_name.lower()}",
                        'meta': model._meta.verbose_name.lower(),
                        'value': f"{model._meta.model_name}.{field.name}"
                    })
                elif field.related_model:
                    for rel_field in field.related_model._meta.fields:
                        if rel_field.name in exclude:
                            continue
                        base.append({
                            'name': rel_field.verbose_name.lower(),
                            'meta': field.related_model._meta.verbose_name.lower(),
                            'value': f"{model._meta.model_name}.{field.name}.{rel_field.name}"
                        })

        return base
