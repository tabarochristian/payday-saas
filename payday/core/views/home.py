from django.utils.translation import gettext as _
from django.shortcuts import render
from core.models import Widget
from .base import BaseView


class Home(BaseView):
    """
    Home view for the application that dynamically renders the homepage with widgets.

    This view retrieves every Widget instance from the database, renders each widget’s
    content with the current request context, and organizes them by their designated
    column. The resulting widget data is then passed to the template for display.
    """
    template_name = "home.html"

    def get(self, request):
        """
        Handle GET requests for the homepage.

        Retrieves all Widget objects and prepares a list where each widget is represented
        as a dictionary containing its title, rendered content, and assigned column.
        The resulting context is then rendered with the specified template.

        Args:
            request (HttpRequest): The HTTP request object.

        Returns:
            HttpResponse: The rendered template response with the widget information.
        """
        # Retrieve all widgets and build a list of dictionaries for each one.
        widgets = [{
            'title': widget.name,
            'content': widget.render(request),
            'column': widget.column,
        } for widget in Widget.objects.all()]
        return render(request, self.template_name, locals())
