from django.utils.translation import gettext as _
from django.shortcuts import render, redirect
from django.http import Http404
from django.contrib import messages
from django.urls import reverse_lazy
from django.db import transaction
from django.contrib.admin.models import CHANGE
from core.forms import modelform_factory, InlineFormSetHelper
from core.forms.button import Button
from core.models import Preference
from .base import BaseView
import logging
import uuid

logger = logging.getLogger(__name__)

class Change(BaseView):
    """
    Enhanced view for updating model instances with improved permission handling,
    error management, and form processing.
    """
    template_name = "change.html"
    inline_formset_helper = InlineFormSetHelper()
    action = ["change"]

    def dispatch(self, request, *args, **kwargs):
        """
        Validates user permissions before processing the request.
        Redirects to read view if permission is lacking.
        """
        model_class = self.get_model()
        change_perm = f"{model_class._meta.app_label}.change_{model_class._meta.model_name}"

        if not request.user.has_perm(change_perm):
            messages.warning(request, _("Vous n'avez pas la permission de modifier cet objet."))
            return redirect(reverse_lazy('core:read', kwargs=kwargs))
        
        self.next = request.GET.get('next')
        return super().dispatch(request, *args, **kwargs)

    def _get_object(self):
        """
        Retrieves model instance with optimized queries and proper error handling.
        
        Raises:
            Http404: If instance not found or no PK provided.
        """
        model_class = self.get_model()
        pk = self.kwargs.get('pk')
        
        if not pk:
            logger.error(f"No primary key provided for {model_class._meta.model_name}")
            raise Http404(_('Aucun identifiant n\'a été fourni'))

        try:
            obj = self.get_queryset().select_related().get(**{model_class._meta.pk.name: pk})
        except model_class.DoesNotExist:
            logger.warning(f"{model_class._meta.model_name} ID {pk} not found")
            raise Http404(_('Le {model} #{pk} n\'existe pas').format(
                model=model_class._meta.model_name, pk=pk))
        
        return obj

    def get_action_buttons(self, obj=None):
        """
        Generates action buttons based on user permissions and model configuration.
        
        Args:
            obj: Model instance to generate buttons for.
            
        Returns:
            List of Button objects for permitted actions.
        """
        obj = obj or self._get_object()
        model_permission_prefix = f"{self.kwargs['app']}.{self.kwargs['model']}"
        
        buttons = [
            Button(
                tag='a',
                text=_('Supprimer'),
                classes='btn btn-light-danger',
                permission=f"{model_permission_prefix}.delete",
                url=reverse_lazy('core:delete', kwargs={
                    'model': self.kwargs['model'],
                    'app': self.kwargs['app'],
                }) + f'?pk__in={self.kwargs['pk']}'
            ),
            Button(
                tag='button',
                text=_('Sauvegarder'),
                classes='btn btn-light-success',
                permission=f"{model_permission_prefix}.change",
                attrs={'type': 'submit', 'form': f"form-{self.kwargs['model']}"}
            )
        ]

        # Handle model-specific extra buttons
        get_action_buttons = getattr(obj, 'get_action_buttons', [])
        extra_buttons = [Button(**button) for button in get_action_buttons]

        return [btn for btn in extra_buttons + buttons]

    def get_formsets(self, obj=None):
        """
        Generates formsets lazily with proper initialization.
        
        Args:
            obj: Model instance to bind formsets to.
            
        Returns:
            List of initialized formset instances.
        """
        obj = obj or self._get_object()
        return [formset(instance=obj) for formset in self.formsets()]

    def validate_form(self, form, formsets):
        """
        Hook for custom form validation. Can be overridden in subclasses.
        
        Returns:
            bool: True if validation passes, False otherwise.
        """
        return True

    def get(self, request, app, model, pk):
        """
        Handles GET requests with optimized form and formset initialization.
        """
        model_class = self.get_model()
        obj = self._get_object()

        # Handle notification-specific behavior
        if model_class._meta.model_name == 'notification':
            obj.mark_as_read()
            return redirect(obj.target.get_absolute_url() if obj.target else reverse_lazy('core:notifications'))

        FormClass = modelform_factory(model_class, fields=self.get_form_fields())
        form = self.filter_form(FormClass(instance=obj))
        formsets = self.get_formsets(obj)
        action_buttons = self.get_action_buttons(obj)
        
        return render(request, self.get_template_name(), locals())

    @transaction.atomic
    def post(self, request, app, model, pk):
        """
        Processes POST requests with atomic transactions and comprehensive error handling.
        """
        model_class = self.get_model()
        obj = self._get_object()
        
        FormClass = modelform_factory(model_class, fields=self.get_form_fields())
        form = self.filter_form(FormClass(request.POST, request.FILES, instance=obj))
        formsets = [formset(request.POST, request.FILES, instance=obj) for formset in self.formsets()]

        # Validate forms and formsets
        if not (form.is_valid() and all(fs.is_valid() for fs in formsets) and self.validate_form(form, formsets)):
            for error in form.errors.values():
                messages.error(request, str(error))
            for fs in formsets:
                for formset_error in fs.errors:
                    messages.error(request, str(formset_error))
            
            return render(request, self.get_template_name(), locals())

        try:
            # Save changes
            instance = form.save()
            for formset in formsets:
                formset.save()

            # Log change
            change_message = self.generate_change_message(obj, form.instance)
            self.log(model_class, form, action=CHANGE, change_message=change_message)
            
            messages.success(request, _('Le {model} #{pk} a été mis à jour avec succès').format(
                model=model_class._meta.model_name, pk=pk))
            
            return redirect(self.next or reverse_lazy('core:list', kwargs={
                'app': app,
                'model': model_class._meta.model_name
            }))
        
        except Exception as e:
            logger.error(f"Error updating {model_class._meta.model_name} ID {pk}: {str(e)}")
            messages.error(request, _("Une erreur est survenue lors de la mise à jour."))
            return render(request, self.get_template_name(), locals())