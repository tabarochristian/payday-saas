from django.utils.translation import gettext as _
from django.shortcuts import render, redirect
from django.apps import apps
from .base import List


class ActionRequired(List):
    """
    A specialized list view for displaying "action required" items.

    This view extends the base List view from the core application, but it
    explicitly sets the URL keyword arguments to use the 'core' app and the
    'actionrequired' model. Additionally, this view disables the display of any
    action buttons by returning an empty list.

    Attributes:
        action (list): A list containing the allowed actions (in this case, ['view']).
    """
    action = ['view']

    def get_model(self):
        return apps.get_model('core', model_name='actionrequired')

    def get_action_buttons(self):
        """
        Overridden to hide any action buttons for this view.

        Returns:
            list: An empty list, meaning no action buttons will be rendered.
        """
        return []

    def get(self, request):
        """
        Handle GET requests by ensuring that the view's keyword arguments are set
        to use the 'core' app and the 'actionrequired' model, then delegate to the 
        parent's get() method.

        Args:
            request (HttpRequest): The current HTTP request.

        Returns:
            HttpResponse: The rendered response from the parent List view.
        """
        # Ensure that the view's kwargs are updated to use the correct app and model.
        self.kwargs.update({'app': 'core', 'model': 'actionrequired'})
        return super().get(request, app='core', model='actionrequired')
