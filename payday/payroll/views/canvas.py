from django.http import HttpResponse
from core.views import BaseView
from employee.models import Employee
import pandas as pd
from django.utils.text import slugify
import json

class Canvas(BaseView):
    """
    A view for generating Excel exports of employee data in various formats.

    This view supports several export methods:
      - tracker(): Generates an Excel file ("canvas.xlsx") that groups employee
                   tracker data by a specified column (default: branch).
      - benefits(): Generates an Excel file ("canvas-items-to-pay.xlsx") based on
                    a predefined set of headers describing benefit-related items.

    The exported Excel files are created on the fly using pandas and xlsxwriter.
    """
    
    # Predefined headers for benefits export.
    headers = [{
        'matricule': None,
        "type d'element": 1,
        'code': None,
        'nom': None,
        'montant quote part employee': 0,
        'montant quote part employeur': 0,
        'plafond de la sécurité sociale': 0,
        'montant imposable': 0,
        'est une prime': 0,
        'est payable': 1,
    }]

    def tracker(self):
        """
        Generate an Excel file that exports employee tracker data.

        The method performs the following steps:
          1. Constructs query parameters from the GET request.
          2. Retrieves employees satisfying these parameters.
          3. Builds a list of dictionaries with selected employee fields plus default values
             for additional columns (e.g. absence-related columns).
          4. Converts the data into a pandas DataFrame.
          5. If the DataFrame is not empty, sorts and groups the data by 'branch' and writes
             each group to a separate sheet in an Excel workbook.

        Returns:
            HttpResponse: An HTTP response with the generated Excel file as an attachment.
        """
        # Construct query parameters from request GET data
        query_params = {
            key: value.split(',') if '__in' in key else value
            for key, value in self.request.GET.dict().items() if value
        }
        if not query_params:
            # If no query parameters are available, warn and redirect.
            messages.warning(self.request, _("Impossible de trouver le modèle d'objet"))
            return redirect(self.request.META.get('HTTP_REFERER'))

        # Retrieve employee objects based on query parameters.
        qs = Employee.objects.filter(**query_params).values(
            'registration_number', 'last_name', 'middle_name', 'branch__name', 'grade__name'
        )

        # Define additional columns for which default values are set.
        additional_columns = ['absence', 'absence.justifiee']
        # For now, assume no columns should get a 'None' default rather than numeric zero.
        field_no_numbers = []

        # Build a list of data dictionaries for each employee.
        data = [{
            'registration_number': obj['registration_number'],
            'last_name': obj['last_name'],
            'middle_name': obj['middle_name'],
            'grade': obj['grade__name'],
            'branch': obj['branch__name'],
            **{col: None if col in field_no_numbers else 0 for col in additional_columns}
        } for obj in qs]

        # Specify the field on which to group the data.
        group_by = 'branch'
        # Convert the list of dictionaries to a pandas DataFrame.
        df = pd.read_json(json.dumps(data), dtype={'registration_number': str})

        if not df.empty:
            # Sort the data by grade, registration number, last name, and middle name.
            df = df.sort_values(
                by=['grade', 'registration_number', 'last_name', 'middle_name'],
                ascending=[True, True, True, True]
            )
            # Group the DataFrame by the specified column.
            df = df.groupby(group_by)

        # Initialize HTTP response for an Excel file download.
        response = HttpResponse(content_type='application/xlsx')
        response['Content-Disposition'] = 'attachment; filename="canvas.xlsx"'.lower()

        with pd.ExcelWriter(response) as writer:
            if group_by:
                # Write each group to a separate sheet.
                for group_value, group_df in df:
                    # Use slugify to generate a valid sheet name.
                    sheet_name = slugify(str(group_value))
                    group_df.to_excel(writer, sheet_name=sheet_name, index=False)
            else:
                # If not grouped, export all data to a single sheet.
                df.to_excel(writer, sheet_name='global', index=False)
        return response

    def benefits(self):
        """
        Generate an Excel file for benefit export based on predefined headers.

        This method:
          1. Converts the predefined headers to a DataFrame.
          2. Writes the DataFrame to an Excel workbook with a single sheet.

        Returns:
            HttpResponse: An HTTP response with the generated Excel file as an attachment.
        """
        # Convert headers to a DataFrame.
        df = pd.read_json(json.dumps(self.headers))
        # Prepare the HTTP response with the appropriate content type.
        response = HttpResponse(content_type='application/xlsx')
        response['Content-Disposition'] = 'attachment; filename="canvas-items-to-pay.xlsx"'.lower()

        with pd.ExcelWriter(response) as writer:
            df.to_excel(writer, sheet_name='global', index=False)
        return response

    def get(self, request, actor):
        """
        Dynamically dispatch to the specified export actor method.

        The 'actor' parameter determines which export functionality to execute
        (e.g., "tracker" or "benefits"). If the specified actor is not callable, raises a 404 error.
        
        Args:
            request (HttpRequest): The incoming HTTP GET request.
            actor (str): The name of the method to invoke.
        
        Returns:
            HttpResponse: The output of the selected export method.
        
        Raises:
            Http404: If the actor is not found or not callable.
        """
        export_method = getattr(self, actor, None)
        if not export_method or not callable(export_method):
            raise Http404("Page not found")
        return export_method()
