from django.shortcuts import render, get_object_or_404
from core.views import BaseViewMixin

from django.contrib.contenttypes.models import ContentType
from django.contrib.admin.models import LogEntry
from employee.models import Employee


class EmployeePrint(BaseViewMixin):
    """
    A view for printing an employee's details along with its activity logs.

    This view retrieves an Employee instance identified by its primary key and
    gathers corresponding log entries from Django Admin's logging system.
    The information is then rendered using a designated template.
    """
    template_name = "employee/sheet.html"

    def get(self, request, pk):
        """
        Handle GET requests to render the employee sheet along with activity logs.

        Args:
            request (HttpRequest): The incoming HTTP GET request.
            pk (int): The primary key of the Employee instance to display.

        Returns:
            HttpResponse: The rendered response containing employee details and logs.
        """
        # Retrieve the Employee object; raise 404 if not found.
        employee_obj = get_object_or_404(Employee, pk=pk)

        # Get the ContentType for the Employee model.
        employee_content_type = ContentType.objects.get_for_model(Employee)

        # Fetch log entries for the employee using its content type and primary key.
        employee_logs = LogEntry.objects.filter(
            content_type_id=employee_content_type.id,
            object_id=pk
        ).values('action_time', 'change_message')

        # Build an explicit context dictionary to pass to the template.
        context = {
            'employee': employee_obj,
            'logs': employee_logs,
        }

        return render(request, self.template_name, context)
