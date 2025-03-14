from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _
from django.http import HttpResponse
from django.contrib import messages
from core.views import BaseView

import xlsxwriter
from io import BytesIO


class Canvas(BaseView):
    """
    A view responsible for generating an Excel file (canvas) based on a given model's layout.
    
    The view retrieves a model's fields based on a defined 'layout' attribute and applies
    Excel data validation rules to each column. Certain fields and field types are excluded 
    from the output.

    Class Attributes:
        MAX_ROWS (int): Maximum number of rows to apply data validation.
        NUMBER_RANGE (tuple): The (min, max) range for numeric fields.
        DATE_RANGE (tuple): The (min, max) range for date fields.
        EXCLUDED_FIELDS (list): Fields to be ignored in the Excel layout.
        EXCLUDED_FIELD_TYPES (list): Field types to be ignored.
    """
    MAX_ROWS = 200
    NUMBER_RANGE = (0, 999999999)
    DATE_RANGE = ('1900-01-01', '2100-12-31')
    EXCLUDED_FIELDS = [
        'created_by', 
        'updated_by', 
        'created_at', 
        'updated_at', 
        '_metadata',
        
        # Employee excluded fields
        'photo',
        'devices',
        'create_user_on_save'
    ]
    EXCLUDED_FIELD_TYPES = [
        'AutoField', 
        'BigAutoField',
        'ManyToManyField',
        'ImageField',
        'FileField',
        'ImporterField',
    ]

    def get(self, request, pk):
        """
        Handle GET requests by generating an Excel file based on the provided model's layout.
        
        Args:
            request (HttpRequest): The HTTP request object.
            pk (int): The primary key of the ContentType to generate the Excel file from.
        
        Returns:
            HttpResponse: A response containing the generated Excel file for download.
        """
        # Retrieve the ContentType object and its corresponding model class
        content_type = get_object_or_404(ContentType, pk=pk)
        model_class = content_type.model_class()

        # Retrieve the model fields based on the defined layout, if available.
        model_fields = self._get_model_fields(model_class)
        if not model_fields:
            messages.error(request, _("Aucun layout n'est défini pour ce modèle."))
            return redirect(request.META.get('HTTP_REFERER'))
        
        # Generate the Excel file based on the model fields.
        output = self._generate_excel(model_fields, model_class)
        
        response = HttpResponse(
            output.read(), 
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        # Set the appropriate filename using the model's verbose name.
        response['Content-Disposition'] = f"attachment; filename={model_class._meta.verbose_name_plural}.xlsx"
        return response

    def _get_model_fields(self, model_class):
        """
        Retrieve a dictionary of fields from the model's layout, excluding fields 
        defined in EXCLUDED_FIELDS.
        
        Args:
            model_class: The Django model class.
        
        Returns:
            dict or None: A dictionary where keys are field names and values are field objects,
                          or None if no layout is defined.
        """
        # Expect the model to have a 'layout' attribute.
        layout = getattr(model_class, 'layout', None)
        if not layout:
            return None
        
        # Retrieve field names from the layout.
        fields = layout.get_field_names()
        
        # Create a dictionary mapping field names to their corresponding field objects.
        model_fields = {field.name: model_class._meta.get_field(field.name) for field in fields}

        # remove photo, file, m2m field in the model canvas

        
        # Remove excluded fields from the dictionary.
        for excluded in self.EXCLUDED_FIELDS:
            model_fields.pop(excluded, None)
        
        return model_fields

    def _generate_excel(self, model_fields, model_class):
        """
        Generate an Excel workbook using xlsxwriter populated with the model fields
        as headers and applying data validations where necessary.
        
        Args:
            model_fields (dict): Dictionary of field names and field objects.
            model_class: The Django model class.
        
        Returns:
            BytesIO: A BytesIO stream containing the Excel file.
        """
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet()

        # Write headers and apply data validations for each column.
        for col_index, (field_name, field) in enumerate(model_fields.items()):
            # Write the header (in uppercase for clarity).
            worksheet.write(0, col_index, field.verbose_name.upper())
            # Apply validation rules for each field.
            self._apply_data_validation(worksheet, col_index, field)
        
        workbook.close()
        output.seek(0)
        return output

    def _is_single_relation_field(self, field):
        """
        Determine if a field represents a single relation.
        
        Args:
            field: The Django model field.
        
        Returns:
            bool: True if the field is a single relation field, False otherwise.
        """
        return field.is_relation and hasattr(field, 'remote_field') and field.remote_field

    def _apply_data_validation(self, worksheet, col_index, field):
        """
        Apply appropriate Excel data validation to a column based on the field's characteristics.
        
        Args:
            worksheet: The xlsxwriter worksheet instance.
            col_index (int): The column index in the worksheet where the field is written.
            field: The Django model field.
        """
        if field.choices:
            # Data validation for choice fields (dropdown list).
            worksheet.data_validation(1, col_index, self.MAX_ROWS, col_index, {
                'validate': 'list',
                'source': [choice[0] for choice in field.choices],
                'input_title': 'Choose one:',
                'input_message': _('Select a value from the list'),
            })

        elif self._is_single_relation_field(field):
            # Data validation for single-relation fields.
            source = list(field.related_model.objects.all().values_list('name', flat=True)[:2])
            worksheet.data_validation(1, col_index, self.MAX_ROWS, col_index, {
                'validate': 'list',
                'source': source,
                'input_title': 'Choose one:',
                'input_message': _('Select a value from the list'),
            })

        elif field.get_internal_type() in ['DateField', 'DateTimeField']:
            # Data validation for date fields, ensuring the date is within the specified range.
            worksheet.data_validation(1, col_index, self.MAX_ROWS, col_index, {
                'validate': 'date',
                'criteria': 'between',
                'minimum': self.DATE_RANGE[0],
                'maximum': self.DATE_RANGE[1],
                'input_title': 'Invalid date',
                'input_message': _('Date must be between {0} and {1}.').format(*self.DATE_RANGE),
            })

        elif field.get_internal_type() in ['IntegerField', 'DecimalField', 'FloatField']:
            # Data validation for numeric fields, ensuring the number is within the allowed range.
            worksheet.data_validation(1, col_index, self.MAX_ROWS, col_index, {
                'validate': 'integer',
                'criteria': 'between',
                'minimum': self.NUMBER_RANGE[0],
                'maximum': self.NUMBER_RANGE[1],
                'input_title': 'Invalid number',
                'input_message': _('Number must be between {0} and {1}.').format(*self.NUMBER_RANGE),
            })
