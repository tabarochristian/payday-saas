from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.apps import apps
from core import views as core_views
from django.http.request import QueryDict


class Notifications(core_views.List):
    """
    A specialized list view to display notifications filtered for the current user.

    This view extends the base List view and configures it to work with the
    'notifications' app and 'notification' model. It overrides the GET method to
    automatically filter notifications by setting the "recipient_id" query
    parameter to the current user's primary key.

    Attributes:
        action (list): The list of allowed actions for this view (e.g., ['view']).
    """
    action = ['view']

    def get_action_buttons(self):
        """
        Return an empty list of action buttons, as no extra actions are needed
        for the notifications view.

        Returns:
            list: An empty list.
        """
        return []

    def get_list_display(self):
        """
        Define the fields to display in the notifications list view.

        Returns:
            list: A sorted list of field objects, based on a predefined ordering.
        """
        model_class = self.get_model()
        list_display = ['actor', 'verb', 'description', 'unread', 'timestamp']
        list_display_order = {field: i for i, field in enumerate(list_display)}
        # Filter the model's fields to include only those specified in "list_display" and sort them.
        return sorted(
            [field for field in model_class._meta.fields if field.name in list_display],
            key=lambda field: list_display_order[field.name]
        )

    def get_list_filter(self):
        """
        Provides the list of fields available for filtering notifications.

        Returns:
            list: A list of field names on which notifications can be filtered.
        """
        return ['unread', 'public']

    def get(self, request):
        """
        Handle GET requests by automatically filtering notifications intended for the current user.

        This method sets up a QueryDict with the "recipient_id" parameter (using the current
        user's primary key), updates the URL keyword arguments to use the 'notifications' app and
        'notification' model, and then delegates the processing to the parent List view.

        Args:
            request (HttpRequest): The HTTP request object.

        Returns:
            HttpResponse: The rendered response from the parent List view.
        """
        # Build a query string to filter notifications for the current recipient.
        query = {"recipient_id": request.user.pk}
        query_string = "&".join([f"{key}={value}" for key, value in query.items()])
        request.GET = QueryDict(query_string)

        # Update the URL keyword arguments to use the correct app and model.
        self.kwargs.update({'app': 'notifications', 'model': 'notification'})
        return super().get(request, app='notifications', model='notification')
