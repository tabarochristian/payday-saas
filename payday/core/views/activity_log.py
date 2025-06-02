from django.utils.translation import gettext as _
from django.contrib.admin.models import LogEntry
from .base import List


class ActivityLog(List):
    """
    A specialized list view to display activity log (audit log) entries.

    This view overrides the base list functionality to configure display and filtering
    for the LogEntry model. It specifies which fields to display, their order, and the
    available filters. The view then relies on the base List view implementation for
    rendering.
    """

    def get_model(self):
        return LogEntry

    def get_list_display(self, model):
        """
        Define the fields to be displayed and order them according to a fixed priority.

        Args:
            model: The model class (typically LogEntry) whose fields are to be displayed.

        Returns:
            list: A sorted list of field objects from model._meta.fields that are included
                  in the display configuration.
        """
        # Fields that we want to display in the activity log.
        list_display = ['action_time', 'content_type', 'object_id', 'change_message', 'user']
        # Create an ordering dictionary for the display fields.
        list_display_order = {field: index for index, field in enumerate(list_display)}
        # Filter the model's fields and sort them using the predefined order.
        return sorted(
            [field for field in model._meta.fields if field.name in list_display],
            key=lambda field: list_display_order[field.name]
        )

    def get_list_filter(self):
        """
        Specify the list of field names that can be used to filter the activity log entries.

        Returns:
            list: A list of field names to use as filters.
        """
        # Provide filtering on content type, action flag, and the timestamp of the action.
        return ['content_type', 'action_flag', 'action_time']

    def get_action_buttons(self):
        return []

    def get(self, request):
        """
        Handle GET requests for the ActivityLog view.

        This method sets the URL kwargs for the 'app' and 'model' to match the LogEntry
        model, then delegates the request to the parent List view's get() method.

        Args:
            request (HttpRequest): The incoming HTTP GET request.

        Returns:
            HttpResponse: The rendered response from the parent list view.
        """
        # Set the required parameters for LogEntry.
        self.kwargs['app'] = LogEntry._meta.app_label
        self.kwargs['model'] = LogEntry._meta.model_name
        # Delegate to the parent view using the LogEntry app label and model name.
        return super().get(request, LogEntry._meta.app_label, LogEntry._meta.model_name)
