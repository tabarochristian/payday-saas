from django.utils.translation import gettext as _
from django.shortcuts import render, redirect, get_object_or_404
from django.apps import apps
import pandas as pd
import json
from core.views import BaseView

# Helper functions with descriptive names.
def intcomma(value):
    """
    Format a numeric value with commas and two decimal places.
    
    Args:
        value (int|float): The numeric value to format.
    
    Returns:
        str: The formatted string if value is a number; otherwise, returns the value as-is.
    """
    return f"{value:,.2f}" if isinstance(value, (int, float)) else value

def get_name_of_fields(field_list):
    """
    Retrieve a list of field names from a list of field objects.
    
    Args:
        field_list (list): List of Django field objects.
    
    Returns:
        list: List of field names.
    """
    return [field.name for field in field_list]


class Synthesis(BaseView):
    """
    A view to generate a pivot-table synthesis report exported as an HTML table.
    
    This view processes employee paid data by pivoting on selected row and column fields,
    aggregating the 'net' values using a specified function, and then adding totals thru rows 
    and columns. The resulting DataFrame is formatted and converted to HTML.
    """
    action = ["view"]
    template_name = "payroll/synthesis.html"
    template_name_field_selector = "payroll/field_selector.html"
    
    def get_field_verbose(self, model, field):
        """
        Recursively retrieves the verbose name of a (possibly nested) field.
        
        Args:
            model: The Django model class.
            field (str): The field name (possibly nested using '__').
            
        Returns:
            str: The verbose name of the field (in lowercase).
        """
        parts = field.split('__')
        if len(parts) == 1:
            return model._meta.get_field(parts[0]).verbose_name.lower()
        related_model = model._meta.get_field(parts[0]).related_model
        return self.get_field_verbose(related_model, '__'.join(parts[1:]))
    
    def get_field(self, model, field):
        """
        Recursively retrieves a Django field object given a (possibly nested) field name.
        
        Args:
            model: The Django model class.
            field (str): The field name (possibly nested using '__').
        
        Returns:
            Field: The Django field object.
        """
        parts = field.split('__')
        if len(parts) == 1:
            return model._meta.get_field(parts[0])
        related_model = model._meta.get_field(parts[0]).related_model
        return self.get_field(related_model, '__'.join(parts[1:]))
    
    def get(self, request, func, pk):
        """
        Render the field selector template, which allows the user to choose which
        fields to include in the synthesis export.
        
        Args:
            request (HttpRequest): The incoming GET request.
            func (str): The name of the aggregation function to use (e.g., 'sum').
            pk (int): The primary key of the payroll instance.
            
        Returns:
            HttpResponse: The rendered field selector page.
        """
        # Retrieve the paidemployee model for payroll.
        model_class = apps.get_model('payroll', 'paidemployee')
        return render(request, self.template_name_field_selector, locals())
    
    def post(self, request, func, pk):
        """
        Process the synthesis export form submission, generate a pivot table based on the
        user's selection, and render the result as HTML.
        
        Steps:
         1. Retrieve the payroll object using pk.
         2. Get the related paidemployee data for that payroll.
         3. Determine which fields the user selected for export (ensuring 'net' is included).
         4. Create a pivot table using pandas with the specified aggregation function.
         5. Append row and column totals.
         6. Format the DataFrame and convert it to an HTML table.
         7. Render the final synthesis using the template.
        
        Args:
            request (HttpRequest): The incoming POST request.
            func (str): The aggregation function to use (e.g., 'sum', 'mean', etc.).
            pk (int): The primary key of the payroll object.
        
        Returns:
            HttpResponse: The rendered synthesis page.
        """
        # Get the payroll object.
        payroll_model = apps.get_model('payroll', 'payroll')
        payroll_obj = payroll_model.objects.get(pk=pk)
        
        # Retrieve the paidemployee records related to the payroll.
        model_class = apps.get_model('payroll', 'paidemployee')
        qs = payroll_obj.paidemployee_set.all().select_related().prefetch_related()
        
        # Extract the selected field names from the POST data, ignoring the CSRF token.
        post_dict = request.POST.dict()
        selected_fields = [value for key, value in post_dict.items() if key != 'csrfmiddlewaretoken']
        if 'net' not in selected_fields:
            selected_fields.append('net')
        
        qs = qs.filter(payroll=payroll_obj)
        data = qs.values(*selected_fields)
        
        # Map each selected field to its verbose name.
        field_verbose_map = {field: self.get_field_verbose(model_class, field) for field in selected_fields}
        
        # Create a DataFrame from the query results.
        df = pd.DataFrame.from_records(data)
        
        # Create a pivot table from the DataFrame.
        pivot_index = request.POST.get('column')
        pivot_columns = request.POST.get('row')
        df_pivot = df.pivot_table(
            index=pivot_index, 
            columns=pivot_columns, 
            values='net', 
            aggfunc=func, 
            fill_value=0
        )
        
        # Add a Total column (sum across rows).
        df_pivot['Total'] = df_pivot.sum(axis=1)
        # Create a total row (sum across columns).
        total_row = df_pivot.sum(axis=0)
        total_row.name = 'Total'
        # Append the total row to the pivot table.
        df_pivot = pd.concat([df_pivot, total_row.to_frame().T])
        
        # Reset index for better readability.
        df_pivot.reset_index(inplace=True)
        # Rename columns using the verbose names.
        df_pivot.rename(columns=field_verbose_map, inplace=True)
        # Remove the multi-index name.
        df_pivot.columns.name = None

        if func == 'sum':
            # Apply numeric formatting if the aggregation function is sum.
            df_pivot = df_pivot.applymap(intcomma)
        
        # Rename the index column to a more human-readable name.
        row_field_verbose = self.get_field_verbose(model_class, request.POST.get('row'))
        df_pivot.rename(columns={'index': row_field_verbose.title()}, inplace=True)
        
        # Convert the pivot table to an HTML table with bootstrap styles.
        html_table = df_pivot.to_html(index=False, classes='table table-striped mt-3')
        # Adjust styling as necessary.
        html_table = html_table.replace('text-align: right;', 'text-align: left;')
        return render(request, self.template_name, locals())