from django.core.exceptions import FieldDoesNotExist
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout
from collections.abc import Sequence
from django import forms

def model_has_field(model_class, field_name):
    try:
        return bool(model_class._meta.get_field(field_name))
    except FieldDoesNotExist:
        return False

def modelform_factory(model, fields=None, exclude=None, layout=None, form_class_name=None, form_tag=True):
    exclude = exclude or []
    layout = layout or getattr(model, 'layout', Layout())

    if model_has_field(model, 'sub_organization') and 'sub_organization' not in layout.fields:
        layout.fields.insert(0, 'sub_organization')
        if isinstance(fields, Sequence) and 'sub_organization' not in fields:
            fields = ['sub_organization', *fields]

    helper = FormHelper()
    helper.layout = layout
    helper.form_tag = form_tag

    Meta = type('Meta', (object,), {
        'model': model,
        'fields': fields or '__all__',
        'exclude': exclude
    })

    return type(
        form_class_name or f"{model._meta.object_name}ModelForm",
        (forms.ModelForm,),
        {'Meta': Meta, 'helper': helper, '__module__': model.__module__}
    )
