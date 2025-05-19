from django.utils.translation import gettext as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout
from django import forms
from django.contrib.auth import get_user_model
from employee.models import Employee

def modelform_factory(model, fields=None, layout=None, form_class_name=None, form_tag=True, request=None):
    """Factory to dynamically create a ModelForm with conditional layouts and auto-prefilled fields."""
    layout = layout or getattr(model, 'layout', Layout())

    helper = FormHelper()
    helper.layout = layout
    helper.form_tag = form_tag

    # Define Meta class with fields and exclusions
    class Meta:
        model = model
        fields = fields or '__all__'

    # Create the ModelForm class dynamically
    form_class_name = form_class_name or f"{model._meta.model_name.capitalize()}ModelForm"

    class GeneratedModelForm(forms.ModelForm):
        Meta = Meta
        helper = helper
        form_tag = 'form' if helper.form_tag else 'div'

        def __init__(self, *args, **kwargs):
            """Automatically fill user-related fields."""
            super().__init__(*args, **kwargs)

            if request and request.user.is_authenticated:
                user = request.user
                employee = Employee.objects.filter(user=user).first()

                for field_name, field in self.fields.items():
                    if field.queryset.model == get_user_model():
                        self.fields[field_name].initial = user
                    elif field.queryset.model == Employee and employee:
                        self.fields[field_name].initial = employee

    return GeneratedModelForm
