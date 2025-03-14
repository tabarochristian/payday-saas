from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import Http404
from django.contrib.admin.models import LogEntry, DELETION
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext as _
from django.urls import reverse_lazy
from core.forms.button import Button
from .base import BaseView


class Delete(BaseView):
    """
    View for handling deletion of model objects based on GET query parameters.
    Requires a 'query' in the GET parameters to define which objects to delete.
    """
    next = None
    action = ["delete"]
    template_name = "delete.html"

    def get_action_buttons(self):
        """
        Constructs the action buttons (Cancel and Supprimer) for the deletion confirmation view.
        Additional buttons from the model are appended thereafter.
        """
        app = self.kwargs['app']
        model_str = self.kwargs['model']
        # Retrieve any additional buttons defined on the model
        extra_buttons = getattr(self.get_model(), 'get_action_buttons()', [])
        extra_buttons = [Button(**button) for button in extra_buttons]

        cancel_button = Button(**{
            'text': _('Cancel'),
            'tag': 'a',
            'url': reverse_lazy('core:list', kwargs={'app': app, 'model': model_str}),
            'classes': 'btn btn-light-success',
        })
        delete_button = Button(**{
            'text': _('Supprimer'),
            'tag': 'button',
            'classes': 'btn btn-danger',
            'permission': f'{app}.delete_{model_str}',
            'attrs': {
                'type': 'submit',
                'form': f'form-{model_str}'
            }
        })
        return [cancel_button, delete_button] + extra_buttons

    def _build_query_params(self, request):
        """
        Build and return a dictionary of query parameters from the GET parameters.
        For keys containing '__in', split the value by commas.
        """
        query_params = {}
        # Use request.GET.dict() to iterate over parameters as key/value strings.
        for key, value in request.GET.dict().items():
            query_params[key] = value.split(',') if '__in' in key else value
        return query_params

    def get(self, request, app, model):
        """
        Handle GET requests by validating the query parameters, building the queryset,
        and rendering the confirmation template.
        """
        model_class = self.get_model()
        query_params = self._build_query_params(request)

        if not query_params:
            raise Http404(_("Query is required for delete action"))

        # Extract and remove the 'next' URL parameter if provided
        next_url = query_params.pop('next', None)

        qs = self.get_queryset().filter(**query_params)
        return render(request, self.template_name, locals())

    def post(self, request, app, model):
        """
        Handle POST requests: validate query parameters, perform deletion,
        log the deletion action, and redirect accordingly.
        """
        model_class = self.get_model()
        query_params = self._build_query_params(request)

        if not query_params:
            raise Http404(_("Query is required for delete action"))

        # Extract 'next' parameter or default to the list view URL.
        next_url = query_params.pop('next', reverse_lazy(
            'core:list',
            kwargs={'app': app, 'model': model_class._meta.model_name}
        ))

        qs = self.get_queryset().filter(**query_params)

        # Log the deletion action using Django's LogEntry.
        # Build a comma-separated string of deleted IDs.
        pk_field = model_class._meta.pk.name
        object_ids = list(qs.values_list(pk_field, flat=True))
        id_str = ", ".join(str(obj_id) for obj_id in object_ids)
        LogEntry.objects.log_action(
            user_id=request.user.id,
            object_id=None,
            content_type_id=ContentType.objects.get_for_model(model_class).id,
            object_repr="Object(s) deletion: " + id_str,
            action_flag=DELETION,
        )

        qs.delete()
        messages.success(request, _("Object(s) deleted"))
        return redirect(next_url)
