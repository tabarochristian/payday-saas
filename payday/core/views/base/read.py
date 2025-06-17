from django.utils.translation import gettext as _
from django.shortcuts import render, redirect
from django.http import Http404
from django.contrib import messages
from django.urls import reverse_lazy
from core.forms import modelform_factory
from core.forms.button import Button
from core.models import Preference
from .change import Change
from .base import BaseView

class Read(Change):
    """
    A read-only view for viewing model instances, inheriting from Change.
    Overrides relevant methods to ensure the form is non-editable.
    """
    action = ["view"]

    def dispatch(self, request, *args, **kwargs):
        """
        Check if the user has permission to view the model instance.
        If not, redirect to the home page with a warning message.
        """
        model_class = self.get_model()
        _perm = f"{model_class._meta.app_label}.view_{model_class._meta.model_name}"

        if not request.user.has_perm(_perm):
            messages.warning(request, _("Vous n'avez pas la permission de modifier cet objet."))
            return redirect(reverse_lazy("core:home"))

        return BaseView.dispatch(self, request, *args, **kwargs)

    
    def get_action_buttons(self, obj=None):
        """
        Constructs action buttons for read-only view.
        Includes only relevant actions like "Cancel" while removing modification buttons.

        Args:
            obj (ModelInstance, optional): The instance for which action buttons are generated.

        Returns:
            list: A list of permitted Button objects.
        """
        obj = obj or self._get_object()
        kwargs = {'app': self.kwargs['app'], 'model': self.kwargs['model']}

        cancel_button = Button(
            tag='a',
            text=_('Annuler'),
            classes='btn btn-light-secondary',
            url=reverse_lazy('core:list', kwargs=kwargs),
            permission=f"{kwargs['app']}.view_{kwargs['model']}"
        )

        return [cancel_button] if self.request.user.has_perm(cancel_button.permission) else []

    def _set_readonly_fields(self, form):
        """
        Set all fields in the form to read-only mode.
        """
        for field in form.fields.values():
            field.widget.attrs['disabled'] = True
            field.widget.attrs['class'] = 'bg-light'

    def get(self, request, app, model, pk):
        """
        Handle GET requests: retrieve the object, apply read-only constraints,
        and render the template.

        Returns:
            HttpResponse: Rendered read-only template.
        """
        model_class = self.get_model()
        obj = self._get_object()

        if not obj:
            messages.warning(request, _('Le {model} #{pk} n\'existe pas').format(model=model_class._meta.model_name, pk=pk))
            return redirect(reverse_lazy('core:list', kwargs={'app': app, 'model': model_class._meta.model_name}))

        FormClass = modelform_factory(model_class, fields=self.get_form_fields(), form_tag=False)
        form = self.filter_form(FormClass(instance=obj))

        self._set_readonly_fields(form)  # Make form fields read-only
        formsets = [formset(instance=obj) for formset in self.formsets()]

        action_buttons = self.get_action_buttons(obj=obj)
        return render(request, self.get_template_name(), locals())
