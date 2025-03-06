from django.utils.translation import gettext as _
from django.shortcuts import render, redirect
from django.http import Http404
from django.contrib import messages
from django.urls import reverse_lazy
from django.db import transaction
import copy

from core.forms.button import Button
from core.forms import modelform_factory, InlineFormSetHelper
from core.models import Preference
from .base import BaseView


class Read(BaseView):
    """
    A view for reading (viewing) a model instance. This view is similar to a change
    view but set up to display read-only details of an object. It applies user field
    permission constraints to disable editing.

    The view depends on the following:
      - self.get_model() to return the model class.
      - self.get_queryset() to return the appropriate QuerySet.
      - self.get_form_fields() and self.formsets() for form and inline formset generation.
      - self.filter_form() to apply additional filtering to the form.
    """
    next = None
    action = ["change"]
    template_name = "change.html"
    inline_formset_helper = InlineFormSetHelper()

    def safe_eval(self, key, value):
        """
        Safely evaluate a value by converting it using a callable specified by key,
        restricting the functions available to the evaluated expression.
        """
        allowed_names = {'int': int, 'float': float, 'str': str, 'bool': bool, 'list': list}
        try:
            # Using f-string to build the expression, then evaluating it in a restricted environment.
            return eval(f'{key}("{value}")', {"__builtins__": allowed_names}, {})
        except Exception:
            return value

    def preferences(self):
        """
        Retrieve application preferences filtered by keys and evaluate their values.
        
        Returns:
            dict: A dictionary mapping lower-case keys to evaluated preference values.
        """
        prefs = Preference.objects.all().values('key', 'value')
        # Build a dictionary using keys from preferences;
        # split the key on ':' and use the first part and last part for the evaluation.
        return {
            pref.get('key').split(':')[0].lower():
                self.safe_eval(pref.get('key').split(':')[-1].lower(), pref.get('value'))
            for pref in prefs
        }

    def _get_object(self):
        """
        Retrieve the model instance using the primary key provided in URL kwargs.
        
        Raises:
            Http404: If no primary key is provided or if no matching instance is found.
        Returns:
            instance: The model instance that matches the provided pk.
        """
        model_class = self.get_model()
        pk = self.kwargs.get('pk', None)
        if not pk:
            raise Http404(_('Aucun identifiant n\'a été fourni'))
        return self.get_queryset().filter(**{model_class._meta.pk.name: pk}).first()

    def get_action_buttons(self):
        """
        Construct and return a list of action buttons to be used in the template.
        Buttons include actions such as "Annuler" (Cancel) and "Supprimer" (Delete),
        merged with any additional buttons provided by the object.
        
        Returns:
            list: A list of Button objects filtered by user permissions.
        """
        obj = self._get_object()
        kwargs = {
            'app': self.kwargs['app'],
            'model': self.kwargs['model']
        }
        # Retrieve any extra buttons defined on the object.
        extra_buttons = getattr(obj, 'get_action_buttons', [])
        extra_buttons = [Button(**button) for button in extra_buttons]

        # Build Cancel and Delete buttons using reverse_lazy for URL resolution.
        # Notice the inner f-string quotes have been adjusted.
        cancel_button = Button(**{
            'text': _('Annuler'),
            'tag': 'a',
            'url': reverse_lazy('core:list', kwargs=kwargs),
            'classes': 'btn btn-light-danger',
            'permission': f'{kwargs["app"]}.view_{kwargs["model"]}'
        })
        delete_button = Button(**{
            'text': _('Supprimer'),
            'tag': 'a',
            'url': f"{reverse_lazy('core:delete', kwargs=kwargs)}?pk__in={obj.pk}",
            'classes': 'btn btn-danger',
            'permission': f'{kwargs["app"]}.delete_{kwargs["model"]}'
        })

        # Merge extra buttons with static ones and filter based on user permissions.
        action_buttons = extra_buttons + [cancel_button, delete_button]
        return [button for button in action_buttons if self.request.user.has_perm(button.permission)]

    def _set_readonly_and_class(self, fields, readonly=True, css_class='bg-dark'):
        """
        Set fields as read-only and apply a CSS class to the widgets.
        
        Args:
            fields (iterable): An iterable of form field objects.
            readonly (bool): Mark the fields as disabled if True.
            css_class (str): The CSS class to apply.
        """
        for field in fields:
            field.widget.attrs['disabled'] = readonly
            field.widget.attrs['class'] = css_class

    def get(self, request, app, model, pk):
        """
        Handle GET requests: retrieve the object, generate the form pre-populated with
        object data, apply filtering and read-only modifications, and render the template.
        
        Args:
            request: The HttpRequest object.
            app (str): The application label.
            model (str): The model name.
            pk (int): The object primary key.
        
        Returns:
            HttpResponse: The rendered template with context.
        """
        model_class = self.get_model()
        obj = self._get_object()
        if not obj:
            message = _('Le {model} #{pk} n\'existe pas')
            messages.warning(request, message.format(model=model_class._meta.model_name, pk=pk))
            return redirect(reverse_lazy('core:list', kwargs={'app': app, 'model': model_class._meta.model_name}))
        
        # Create an instance of the form with initial data from the object.
        FormClass = modelform_factory(model_class, fields=self.get_form_fields(), form_tag=False)
        form = FormClass(instance=obj)
        form = self.filter_form(form)
        # Set all fields as read-only.
        self._set_readonly_and_class(form.fields.values())
        # Build inline formsets.
        formsets = [formset(instance=obj) for formset in self.formsets()]
        return render(request, self.get_template_name(), locals())
