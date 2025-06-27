from django.utils.translation import gettext as _
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import render, redirect
from django.db import transaction
from django.contrib.admin.models import ADDITION
from core.forms import modelform_factory, InlineFormSetHelper
from core.forms.button import Button
from .base import BaseView
import logging
import uuid

logger = logging.getLogger(__name__)

class Create(BaseView):
    """
    Enhanced view for creating model instances with improved form handling and validation.
    """
    template_name = "create.html"
    inline_formset_helper = InlineFormSetHelper()
    action = ["add"]

    def dispatch(self, request, *args, **kwargs):
        """
        Validates user permissions before processing the request.
        """
        model_class = self.get_model()
        add_perm = f"{model_class._meta.app_label}.add_{model_class._meta.model_name}"

        if not request.user.has_perm(add_perm):
            messages.warning(request, _("Vous n'avez pas la permission de créer cet objet."))
            return redirect(reverse_lazy("core:home"))
        
        self.next = request.GET.get('next')
        return super().dispatch(request, *args, **kwargs)

    def get_action_buttons(self, obj=None):
        """
        Generates action buttons based on user permissions and model configuration.
        
        Args:
            obj: Optional model instance for context-specific buttons.
            
        Returns:
            List of Button objects for permitted actions.
        """
        model_permission_prefix = f"{self.kwargs['app']}.{self.kwargs['model']}"
        
        buttons = [
            Button(
                text=_('Annuler'),
                tag='a',
                url=reverse_lazy('core:list', kwargs={
                    'app': self.kwargs['app'],
                    'model': self.kwargs['model']
                }),
                classes='btn btn-light-danger',
                permission=f"{model_permission_prefix}.view"
            ),
            Button(
                text=_('Sauvegarder'),
                tag='button',
                classes='btn btn-success',
                permission=f"{model_permission_prefix}.add",
                attrs={'type': 'submit', 'form': f"form-{self.kwargs['model']}"}
            )
        ]

        # Handle model-specific extra buttons
        model = self.get_model()
        get_action_buttons = getattr(obj, 'get_action_buttons', [])
        extra_buttons = [Button(**button) for button in get_action_buttons]

        return [btn for btn in extra_buttons + buttons]

    def get_initial_data(self, request):
        """
        Generates initial data for the form.
        
        Returns:
            Dict containing initial form data.
        """
        return {
            'employee': getattr(request.user, 'employee', None),
            **request.GET.dict()
        }

    def validate_form(self, form, formsets):
        """
        Hook for custom form validation. Can be overridden in subclasses.
        
        Returns:
            bool: True if validation passes, False otherwise.
        """
        return True

    def get(self, request, app, model):
        """
        Handles GET requests with optimized form initialization.
        """
        model_class = self.get_model()
        FormClass = modelform_factory(model_class, fields=self.get_form_fields())
        form = self.filter_form(FormClass(initial=self.get_initial_data(request)))
        formsets = [formset() for formset in self.formsets()]
        action_buttons = self.get_action_buttons()
        
        return render(request, self.get_template_name(), locals())

    # @transaction.atomic
    def post(self, request, app, model):
        """
        Processes POST requests with atomic transactions and comprehensive error handling.
        """
        model_class = self.get_model()
        action_buttons = self.get_action_buttons()
        FormClass = modelform_factory(model_class, fields=self.get_form_fields())
        form = self.filter_form(FormClass(
            request.POST,
            request.FILES,
            initial=self.get_initial_data(request)
        ))
        formsets = [formset(request.POST, request.FILES) for formset in self.formsets()]

        # Validate forms and formsets
        if not (form.is_valid() and all(fs.is_valid() for fs in formsets) and self.validate_form(form, formsets)):
            for error in form.errors.values():
                messages.error(request, str(error))
            for fs in formsets:
                for formset_error in fs.errors:
                    messages.error(request, str(formset_error))
            
            return render(request, self.get_template_name(), locals())

        try:
            # Save main instance
            instance = form.save()
            
            # Save inline formsets
            for formset in formsets:
                for obj in formset.save(commit=False):
                    setattr(obj, formset.fk.name, instance)
                    obj.save()
                formset.save_m2m()

            # Log addition
            message = _('Ajout du/de {model} #{pk}').format(
                model=model_class._meta.model_name, pk=instance.pk)
            message = self.generate_change_message(instance, form.instance) or f"#Obj {instance.pk} created"
            self.log(model_class, form, action=ADDITION, change_message=message)
            messages.success(request, message)
            
            return redirect(self.next or reverse_lazy('core:list', kwargs={
                'app': app,
                'model': model_class._meta.model_name
            }))
        
        except Exception as e:
            logger.error(f"Error creating {model_class._meta.model_name}: {str(e)}")
            messages.error(request, _("Une erreur est survenue lors de la création."))
            return render(request, self.get_template_name(), locals())