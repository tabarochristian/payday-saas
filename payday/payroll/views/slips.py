from django.utils.translation import gettext as _
from django.shortcuts import render
from django.http import Http404
from django.apps import apps
from core.views import BaseView


class Slips(BaseView):
    """
    A view that displays payslip information for paid employees.

    This view retrieves the queryset of paid employee records filtered by the GET
    query parameters. If no records are found, it raises a 404 error.
    
    The template used to render the payslips is defined by the `template_name` attribute.
    """
    template_name = "payroll/slip.html"

    def get(self, request):
        """
        Handle GET requests to display payslip data.

        This method:
          1. Sets the appropriate 'app' and 'model' values within the view's keyword arguments.
          2. Retrieves the paid employee model using Django's apps registry.
          3. Filters the model's objects based on GET query parameters.
          4. Raises a 404 error if no records are found.
          5. Renders the template with an explicit context dictionary.
          
        Args:
            request (HttpRequest): The incoming GET request.

        Returns:
            HttpResponse: The rendered payslip view page.
        """
        # Define target app and model
        app = 'payroll'
        model_name = 'paidemployee'
        self.kwargs.update({'app': app, 'model': model_name})
        
        # Retrieve the model class dynamically.
        model_class = apps.get_model(app, model_name)
        # Extract query parameters from the GET request.
        query_params = request.GET.dict()

        # transforms the query parameters to filter the queryset
        query_params = {key: value.split(',') if '__in' in key else value
                    for key, value in query_params.items()}

        # Filter the queryset from the model using the query parameters.
        qs = model_class.objects.filter(**query_params)
        
        # If the queryset is empty, raise a 404 error.
        if not qs.exists():
            raise Http404(_("No payslips found"))

        return render(request, self.template_name, locals())
