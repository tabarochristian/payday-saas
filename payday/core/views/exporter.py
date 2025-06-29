import re
import pandas as pd
from io import BytesIO

from django.utils.translation import gettext as _
from django.shortcuts import render, HttpResponse, redirect
from django.utils.text import slugify
from django.apps import apps

from core.filters import filter_set_factory
from core.models import Base
from .base.base import BaseViewMixin


# Helper functions
def get_name_of_fields(field_list):
    """Return a list of field names from a list of field objects."""
    return [field.name for field in field_list]


def remove_special_chars(value):
    """
    Remove any characters from the string that are not alphanumeric
    or whitespace. If the value is not a string, return it as-is.
    """
    if isinstance(value, str):
        return re.sub(r'[^a-zA-Z0-9\s]', ' ', value)
    return value


class Exporter(BaseViewMixin):
    """
    A view that exports data from a given model to an Excel file.
    
    This view uses a model's layout to determine which fields to export,
    applies filtering based on GET parameters, and generates a formatted
    Excel file with validation and data cleaning.
    
    Attributes:
        action (list): List of allowed actions, e.g. ["view"].
        template_name (str): The template used for rendering the export form.
    """
    action = ["view"]
    template_name = "export.html"

    def get_fields(self):
        """
        Retrieve the list of exportable fields from the model, excluding
        those defined in the Base model.
        
        Returns:
            list: A list of field objects that are editable and not excluded.
        """
        model_class = self.model_class()
        excluded_fields = [field.name for field in Base._meta.fields]
        return [
            field for field in model_class._meta.fields 
            if field.editable and field.name not in excluded_fields
        ]

    def get_field_verbose(self, model_class, field_name):
        """
        Recursively determine the verbose name for a field which may
        reference a related model using '__' notation.
        
        Args:
            model_class: The model class containing the field.
            field_name (str): The field name, possibly nested (using '__').
        
        Returns:
            str: The verbose name of the field in lower case.
        """
        parts = field_name.split('__')
        if len(parts) == 1:
            return model_class._meta.get_field(parts[0]).verbose_name.lower()
        # Get the related model and process the remaining field portion recursively.
        related_model = model_class._meta.get_field(parts[0]).related_model
        return self.get_field_verbose(related_model, '__'.join(parts[1:]))

    def get_field(self, model_class, field_name):
        """
        Retrieve the actual model field object from potentially nested field names.
        
        Args:
            model_class: The model class.
            field_name (str): Field name, possibly nested using '__'.
        
        Returns:
            Field: The model field.
        """
        parts = field_name.split('__')
        if len(parts) == 1:
            return model_class._meta.get_field(parts[0])
        related_model = model_class._meta.get_field(parts[0]).related_model
        return self.get_field(related_model, '__'.join(parts[1:]))

    def get_model_verbose_from_field(self, model_class, field_name):
        """
        Return the verbose name of the model that corresponds to a given field.
        This is typically used for foreign key fields.
        
        Args:
            model_class: The initial model class.
            field_name (str): The field name in '__' notation.
            
        Returns:
            str: The verbose name (in lower case) of the related model.
        """
        field_obj = self.get_field(model_class, field_name)
        # Extract model information from the field's string representation.
        parts = str(field_obj).split('.')[:2]
        related_model = apps.get_model(*parts)
        return related_model._meta.verbose_name.lower()

    def get(self, request, app, model):
        """
        Display the export form.
        
        Args:
            request (HttpRequest): The incoming request.
            app (str): The application label.
            model (str): The model name.
            
        Returns:
            HttpResponse: Rendered export form.
        """
        # Retrieve the model class.
        model_class = apps.get_model(app, model)
        return render(request, self.template_name, locals())

    def post(self, request, app, model):
        """
        Process the export form submission, filter/query data from the model,
        generate an Excel file using pandas and return it as an HTTP response.
        
        Args:
            request (HttpRequest): The incoming request.
            app (str): Application label.
            model (str): Model name.
        
        Returns:
            HttpResponse: A response with the Excel file attachment.
        """
        # Retrieve the model class.
        model_class = apps.get_model(app, model)
        list_filter = getattr(model_class, 'list_filter', [])

        # Prepare the base queryset with related objects.
        qs = model_class.objects.select_related().prefetch_related()
        qs = qs._all(user=request.user, subdomain=request.subdomain) if hasattr(qs, '_all') else qs.all()

        # Retrieve groupBy parameter if present.
        group_by = request.POST.get('groupBy', None)
        # Get all field names for the model.
        model_field_names = [field.name for field in model_class._meta.fields]

        # Build query dictionary from GET parameters (only include recognized fields).
        query_params = request.GET.dict()
        qs = qs.filter(**query_params)

        # Apply additional filtering using a filter set.
        filter_set = filter_set_factory(model_class, fields=list_filter)
        qs = filter_set(request.GET, queryset=qs).qs

        # Determine output fields from POST data excluding irrelevant keys.
        selected_fields = [
            k for k, v in request.POST.dict().items() 
            if k not in ['csrfmiddlewaretoken', 'groupBy']
        ]
        if not selected_fields:
            raise ValueError(_("Please select at least one field to export"))
        if group_by and group_by not in selected_fields:
            selected_fields.append(group_by)
        
        # Retrieve data from the queryset.
        data = qs.values(*selected_fields)

        # Build a mapping of field names to a user-friendly header using verbose names.
        header_mapping = {
            field: f"{self.get_model_verbose_from_field(model_class, field)}.{self.get_field_verbose(model_class, field)}"
            for field in selected_fields
        }

        # Create a DataFrame from the queryset data.
        df = pd.DataFrame.from_records(data).astype(str)
        # Rename the DataFrame columns to the header mapping.
        df.rename(columns=header_mapping, inplace=True)
        # Remove any special characters from the DataFrame
        df = df.applymap(remove_special_chars)
        df.astype(str)

        # Create a filename based on the model's verbose name.
        filename = f"{slugify(model_class._meta.verbose_name)}.xlsx"
        response = HttpResponse(content_type='application/xlsx')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        # Write the DataFrame to an Excel file.
        with pd.ExcelWriter(response) as writer:
            if group_by:
                # If grouping is requested, write each group to its own sheet.
                for group_name, group_df in df.groupby(header_mapping.get(group_by)):
                    group_df.to_excel(writer, sheet_name=str(group_name), index=False)
            else:
                df.to_excel(writer, index=False)
        return response
