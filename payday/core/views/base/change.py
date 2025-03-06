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
import copy
import logging

logger = logging.getLogger(__name__)


class Change(BaseView):
    """
    A view for changing/updating a model instance.

    This view supports GET and POST requests to update an object while applying 
    data filtering, inline formsets, and logging of changes. It also dynamically 
    builds action buttons based on the object's properties and user permissions.
    """
    next = None
    action = ["change"]
    template_name = "change.html"
    inline_formset_helper = InlineFormSetHelper()

    def safe_eval(self, key, value):
        """
        Safely evaluate a value using a restricted set of allowed conversion functions.

        Args:
            key (str): The name of the conversion function to use (e.g., "int", "float").
            value (str): The value (as a string) to be converted.

        Returns:
            The evaluated value if successful; otherwise, returns the original value.
        """
        allowed_names = {'int': int, 'float': float, 'str': str, 'bool': bool, 'list': list}
        try:
            return eval(f'{key}("{value}")', {"__builtins__": allowed_names}, {})
        except Exception as e:
            messages.error(self.request, _('Error in evaluating value: ') + str(e))
            logger.error(f"Error in evaluating value: {e}")
            return value

    def preferences(self):
        """
        Retrieve evaluated application preferences from the database.

        Returns:
            dict: A dictionary mapping processed keys to their evaluated values.
        """
        prefs = Preference.objects.all().values('key', 'value')
        return {
            pref.get('key').split(':')[0].lower():
                self.safe_eval(pref.get('key').split(':')[-1].lower(), pref.get('value'))
            for pref in prefs
        }

    def _get_object(self):
        """
        Retrieve the model instance based on the primary key in URL keyword arguments.

        Raises:
            Http404: If no primary key is provided or no matching instance is found.
        
        Returns:
            instance: The model instance, or None if not found.
        """
        model_class = self.get_model()
        pk = self.kwargs.get('pk', None)
        if not pk:
            raise Http404(_('Aucun identifiant n\'a été fourni'))
        return self.get_queryset().filter(**{model_class._meta.pk.name: pk}).first()

    def get_action_buttons(self):
        """
        Constructs a list of action buttons (e.g. Delete, Save) for the change view.

        Returns:
            list: A list of Button objects filtered by user permissions.
        """
        obj = self._get_object()
        kwargs = {'app': self.kwargs['app'], 'model': self.kwargs['model']}

        # Get additional buttons defined on the object, if any.
        extra_buttons = getattr(obj, 'get_action_buttons', [])
        extra_buttons = [Button(**button) for button in extra_buttons]

        # Define standard action buttons.
        delete_button = Button(**{
            'text': _('Supprimer'),
            'tag': 'a',
            'url': reverse_lazy('core:delete', kwargs=kwargs) + f'?pk__in={obj.pk}',
            'classes': 'btn btn-light-danger',
            'permission': f'{kwargs["app"]}.delete_{kwargs["model"]}'
        })
        save_button = Button(**{
            'text': _('Sauvegarder'),
            'tag': 'button',
            'classes': 'btn btn-light-success',
            'permission': f'{kwargs["app"]}.change_{kwargs["model"]}',
            'attrs': {
                'type': 'submit',
                'form': f'form-{kwargs["model"]}'
            }
        })

        action_buttons = extra_buttons + [delete_button, save_button]
        # Return only those buttons for which the user has the required permissions.
        return [button for button in action_buttons if self.request.user.has_perm(button.permission)]

    def get(self, request, app, model, pk):
        """
        Handle GET requests by rendering a pre-populated change form and inline formsets.

        Args:
            request (HttpRequest): The incoming request.
            app (str): The application label.
            model (str): The model name.
            pk (int): The primary key of the instance to update.

        Returns:
            HttpResponse: The rendered response with the form and inline formsets.
        """
        model_class = self.get_model()
        obj = self._get_object()

        if not obj:
            warning_msg = _('Le {model} #{pk} n\'existe pas').format(model=model_class._meta.model_name, pk=pk)
            messages.warning(request, warning_msg)
            return redirect(reverse_lazy('core:list', kwargs={'app': app, 'model': model_class._meta.model_name}))

        if model_class._meta.model_name == 'notification':
            obj.mark_as_read()
            if not obj.target:
                return redirect(reverse_lazy('core:notifications'))
            return redirect(obj.target.get_absolute_url())

        # Build and process the main form.
        FormClass = modelform_factory(model_class, fields=self.get_form_fields())
        form = FormClass(instance=obj)
        form = self.filter_form(form)

        # Build inline formsets.
        formsets = [fs(instance=obj) for fs in self.formsets()]
        return render(request, self.get_template_name(), locals())

    @transaction.atomic
    def post(self, request, app, model, pk):
        """
        Handle POST requests to update an instance.

        Validates both the main form and any inline formsets. If valid, saves the
        updates, logs the change, and redirects to the list view; otherwise, re-renders
        the form with warnings.

        Args:
            request (HttpRequest): The incoming request.
            app (str): The application label.
            model (str): The model name.
            pk (int): The primary key of the instance to update.

        Returns:
            HttpResponse or HttpResponseRedirect: Either a re-rendered form (if validation fails)
            or a redirect response on success.
        """
        model_class = self.get_model()
        obj = self._get_object()

        # Preserve a copy of the original object for logging purposes.
        original_instance = copy.copy(obj)
        
        # Build and bind the main form.
        FormClass = modelform_factory(model_class, fields=self.get_form_fields())
        form = FormClass(request.POST or None, request.FILES or None, instance=obj)
        form = self.filter_form(form)

        # Build inline formsets with POST data.
        formsets = [fs(request.POST or None, request.FILES or None, instance=obj) for fs in self.formsets()]

        if not all(fs.is_valid() for fs in [form] + formsets):
            for error in form.errors:
                messages.warning(request, str(error))
            return render(request, self.get_template_name(), locals())

        # Save the main form and all inline formsets.
        form.save()
        for fs in formsets:
            fs.save()

        # Log the change
        change_message = self.generate_change_message(original_instance, form.instance)
        self.log(model_class, form, action=CHANGE, change_message=change_message)
        success_msg = _('Le {model} #{pk} a été mis à jour avec succès').format(model=model_class._meta.model_name, pk=pk)
        messages.success(request, success_msg)

        redirect_to = reverse_lazy('core:list', kwargs={'app': app, 'model': model_class._meta.model_name})
        next_url = request.GET.dict().get('next', redirect_to)
        return redirect(next_url)
