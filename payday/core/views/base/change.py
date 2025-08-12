import logging
from copy import deepcopy

from django.utils.translation import gettext as _
from django.shortcuts import render, redirect
from django.contrib.admin.models import CHANGE
from django.urls import reverse_lazy
from django.contrib import messages
from django.db import transaction
from django.http import Http404

from core.forms import modelform_factory, InlineFormSetHelper
from core.forms.button import Button
from .base import BaseViewMixin

logger = logging.getLogger(__name__)


class Change(BaseViewMixin):
    """
    Enhanced view for updating model instances with optimized permission handling,
    reduced duplicate lookups, and improved form/formset management.
    """
    inline_formset_helper = InlineFormSetHelper()
    template_name = "change.html"
    action = ["change"]

    # ---------------------------------
    # Request Dispatch & Permissions
    # ---------------------------------

    def dispatch(self, request, *args, **kwargs):
        self.model_class_obj = self.model_class()  # cache for reuse
        self.obj_instance = None  # lazy-loaded in _get_object()

        change_perm = f"{self.model_class_obj._meta.app_label}.change_{self.model_class_obj._meta.model_name}"
        if not request.user.has_perm(change_perm):
            messages.warning(request, _("Vous n'avez pas la permission de modifier cet objet."))
            return redirect(reverse_lazy('core:read', kwargs={
                'app': self.model_class_obj._meta.app_label,
                'model': self.model_class_obj._meta.model_name
            }))
        return super().dispatch(request, *args, **kwargs)

    # ---------------------------------
    # Data Retrieval
    # ---------------------------------

    def _get_object(self):
        if self.obj_instance:
            return self.obj_instance

        pk = self.kwargs.get('pk')
        if not pk:
            logger.error("No primary key provided for %s", self.model_class_obj._meta.model_name)
            raise Http404(_("Aucun identifiant n'a été fourni"))

        try:
            self.obj_instance = self.get_queryset().select_related().get(
                **{self.model_class_obj._meta.pk.name: pk}
            )
        except self.model_class_obj.DoesNotExist:
            logger.warning("%s ID %s not found", self.model_class_obj._meta.model_name, pk)
            raise Http404(
                _('Le {model} #{pk} n\'existe pas').format(
                    model=self.model_class_obj._meta.model_name, pk=pk
                )
            )
        return self.obj_instance

    # ---------------------------------
    # Permissions
    # ---------------------------------

    def can_change(self):
        obj = self._get_object()
        return (
            (self.request.user.is_staff or self.request.user.is_superuser)
            and (
                self.approvals().filter(user=self.request.user).exists()
                or getattr(obj, "status", "PENDING") != "APPROVED"
            )
        )

    # ---------------------------------
    # Action Buttons
    # ---------------------------------

    def get_action_buttons(self, obj=None):
        obj = obj or self._get_object()
        app_label, model_name = self.kwargs['app'], self.kwargs['model']
        pk = self.kwargs['pk']

        buttons = [
            Button(
                tag='a',
                text=_('Supprimer'),
                classes='btn btn-light-danger',
                permission=f"{app_label}.delete_{model_name}",
                url=reverse_lazy('core:delete', kwargs={
                    'model': model_name,
                    'app': app_label
                }) + f'?pk__in={pk}'
            )
        ]

        if self.can_change():
            buttons.append(
                Button(
                    tag='button',
                    text=_('Sauvegarder'),
                    classes='btn btn-light-success',
                    permission=f"{app_label}.change_{model_name}",
                    attrs={'type': 'submit', 'form': f"form-{model_name}"}
                )
            )

        extra_buttons = getattr(obj, 'get_action_buttons', [])
        extra_buttons = [Button(**b) for b in extra_buttons] if isinstance(extra_buttons, list) else []

        return extra_buttons + buttons

    # ---------------------------------
    # Form Helpers
    # ---------------------------------

    def validate_form(self, form, formsets):
        return True

    def get_initial_data(self, request):
        initial = request.GET.dict()
        if hasattr(request.user, 'employee'):
            initial['employee'] = request.user.employee
        if getattr(request, 'suborganizations', None) and getattr(request, 'suborganization', None):
            initial['sub_organization'] = request.suborganization.pk
        return initial

    def _build_form_and_formsets(self, obj, data=None, files=None):
        """Centralized creation of main form and inline formsets."""
        FormClass = modelform_factory(self.model_class_obj, fields=self.get_form_fields())
        form = self.filter_form(FormClass(data, files, instance=obj) if data else FormClass(instance=obj))
        formsets = [
            fs(data, files, instance=obj) if data else fs(instance=obj)
            for fs in self.formsets()
        ]
        return form, formsets

    # ---------------------------------
    # HTTP Handlers
    # ---------------------------------

    def get(self, request, app, model, pk):
        obj = self._get_object()

        # Notification special case
        if self.model_class_obj._meta.model_name == 'notification':
            obj.mark_as_read()
            return redirect(obj.target.get_absolute_url() if obj.target else reverse_lazy('core:notifications'))

        form, formsets = self._build_form_and_formsets(obj)
        context = {
            'form': form,
            'formsets': formsets,
            'action_buttons': self.get_action_buttons(obj),
            'object': obj
        }
        return render(request, self.get_template_name(), context)

    @transaction.atomic
    def post(self, request, app, model, pk):
        obj = self._get_object()
        _obj_copy = deepcopy(obj)

        form, formsets = self._build_form_and_formsets(obj, data=request.POST, files=request.FILES)

        if not (form.is_valid() and all(fs.is_valid() for fs in formsets) and self.validate_form(form, formsets)):
            for error in form.errors.values():
                messages.error(request, str(error))
            for fs in formsets:
                for fs_error in fs.errors:
                    messages.error(request, str(fs_error))
            return render(request, self.get_template_name(), locals())

        try:
            instance = form.save()
            for fs in formsets:
                fs.save()

            change_msg = self.generate_change_message(_obj_copy, instance)
            self.log(self.model_class_obj, form, action=CHANGE, change_message=change_msg)

            messages.success(request, _('Le {model} #{pk} a été mis à jour avec succès').format(
                model=self.model_class_obj._meta.model_name, pk=pk
            ))

            next_url = request.GET.get('next')
            return redirect(next_url or reverse_lazy('core:list', kwargs={
                'app': app,
                'model': self.model_class_obj._meta.model_name
            }))
        except Exception as e:
            logger.error("Error updating %s ID %s", self.model_class_obj._meta.model_name, pk, exc_info=True)
            messages.error(request, _("Une erreur est survenue lors de la mise à jour."))
            return render(request, self.get_template_name(), locals())
