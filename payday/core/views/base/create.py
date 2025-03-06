from django.utils.translation import gettext as _
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.admin.models import ADDITION
from django.db import transaction
from core.forms import modelform_factory, InlineFormSetHelper
from core.forms.button import Button
from .base import BaseView


class Create(BaseView):
    """
    View for creating a new instance of a model, with support for inline formsets.
    """
    next = None
    action = ["add"]
    template_name = "create.html"
    inline_formset_helper = InlineFormSetHelper()

    def get_action_buttons(self):
        """
        Build and return the list of action buttons for the create view.
        This typically includes a "Cancel" button, a "Save" button, and any
        extra buttons defined on the model.
        """
        kwargs = {'app': self.kwargs['app'], 'model': self.kwargs['model']}
        
        # Cancel button: redirects back to the list view.
        cancel_button = Button(**{
            'text': _('Annuler'),
            'tag': 'a',
            'url': reverse_lazy('core:list', kwargs=kwargs),
            'classes': 'btn btn-light-danger',
            'permission': 'delete'
        })
        # Save button: submits the form.
        save_button = Button(**{
            'text': _('Sauvegarder'),
            'tag': 'button',
            'classes': 'btn btn-success',
            # Use double quotes for the outer f-string to allow single quotes inside.
            'permission': f"{kwargs['app']}.add_{kwargs['model']}",
            'attrs': {
                'type': 'submit',
                'form': f"form-{kwargs['model']}"
            }
        })
        # Append any additional buttons from the model.
        extra_buttons = []
        buttons_from_model = getattr(self.get_model(), 'get_action_buttons()', [])
        extra_buttons = [Button(**button) for button in buttons_from_model]
        
        return [cancel_button, save_button] + extra_buttons

    def get(self, request, app, model):
        """
        Handle GET requests by initializing the form and any configured inline formsets.
        The form initial values are taken from GET parameters.
        """
        model_class = self.get_model()

        FormClass = modelform_factory(model_class, fields=self.get_form_fields())
        form = FormClass(initial=request.GET.dict())
        form = self.filter_form(form)
        
        # Instantiate inline formsets without POST data.
        formsets = [formset() for formset in self.formsets()]
        return render(request, self.get_template_name(), locals())
    
    @transaction.atomic
    def post(self, request, app, model):
        """
        Process the form submission (POST). Validate the main form and inline formsets,
        save the model instance, and then save all inline instances, associating them
        with the main instance. Logs the addition action and redirects to the list view.
        """
        model_class = self.get_model()

        FormClass = modelform_factory(model_class, fields=self.get_form_fields())
        form = FormClass(request.POST or None, request.FILES or None)
        form = self.filter_form(form)
        
        # Instantiate inline formsets with POST data.
        formsets = [formset(request.POST or None, request.FILES or None) for formset in self.formsets()]

        if not all(fs.is_valid() for fs in [form] + formsets):
            # Add warnings for any errors and re-render the form.
            for error in form.errors:
                messages.warning(request, str(error))
            return render(request, self.get_template_name(), locals())

        # Save main form instance.
        instance = form.save()
        # Save any inline formset instances.
        for formset in formsets:
            inline_instances = formset.save(commit=False)
            for obj in inline_instances:
                setattr(obj, formset.fk.name, instance)
                obj.save()

        # Log the addition.
        message = _('Ajout du/de {model} #{pk}')
        self.log(model_class, form, action=ADDITION, change_message=self.generate_change_message(instance, form.instance))
        messages.success(request, message.format(model=model_class._meta.model_name, pk=instance.pk))

        # Determine redirect URL.
        redirect_url = reverse_lazy('core:list', kwargs={'app': app, 'model': model_class._meta.model_name})
        next_param = request.GET.dict().get('next')
        return redirect(next_param if next_param else redirect_url)
