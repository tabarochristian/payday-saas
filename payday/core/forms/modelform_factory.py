from django.core.exceptions import FieldDoesNotExist
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout
from collections.abc import Sequence
from django import forms

# Import GeoDjango field types safely
try:
    from django.contrib.gis.db.models import GeometryField
    SPATIAL_FIELD_TYPES = (GeometryField,)
except ImportError:
    class GeometryField: 
        pass
    SPATIAL_FIELD_TYPES = (GeometryField,)


# --- PRIORITY: Use MapboxPointFieldWidget (Includes Search/Geocoding) ---
try:
    from mapwidgets.widgets import MapboxPointFieldWidget

    # 1. Create a class that inherits from the Leaflet widget
    class SearchableLeafletWidget(MapboxPointFieldWidget):
        def __init__(self, *args, **kwargs):
            attrs = kwargs.get("attrs", {})
            
            # 2. Force dimensions to prevent the "width or height are 0" error
            attrs.setdefault("style", "height: 400px; width: 100%; display: block;")
            attrs.setdefault("map_width", "100%")
            attrs.setdefault("map_height", "400px")
            
            kwargs["attrs"] = attrs
            super().__init__(*args, **kwargs)

    SPATIAL_WIDGET = SearchableLeafletWidget

except ImportError:
    # --- FALLBACK: Use the fixed OSMWidget if mapwidgets is not installed ---
    try:
        from django.contrib.gis.forms import OSMWidget
        
        class FixedOSMWidget(OSMWidget):
            def __init__(self, *args, **kwargs):
                attrs = kwargs.get("attrs", {})
                attrs.setdefault("style", "height: 400px; width: 100%; display: block;")
                kwargs["attrs"] = attrs
                super().__init__(*args, **kwargs)
        
        SPATIAL_WIDGET = FixedOSMWidget
        
    except ImportError:
        SPATIAL_WIDGET = forms.TextInput


def model_has_field(model_class, field_name):
    # ... (function body remains unchanged) ...
    try:
        return bool(model_class._meta.get_field(field_name))
    except FieldDoesNotExist:
        return False


def get_dynamic_fields(model_class, field_types_to_find):
    # ... (function body remains unchanged) ...
    """Dynamically finds field names on the model that match the specified types."""
    found_fields = []
    for field in model_class._meta.fields:
        if isinstance(field, field_types_to_find):
            found_fields.append(field.name)
    return found_fields


def modelform_factory(model, fields=None, exclude=None, layout=None, form_class_name=None, form_tag=True):
    exclude = exclude or []
    layout = layout or getattr(model, 'layout', Layout())
    
    dynamic_prefix_fields = []
    spatial_field_names = []
    dynamic_widgets = {}

    # --- 1. Handle 'sub_organization' ---
    if model_has_field(model, 'sub_organization'):
        dynamic_prefix_fields.append('sub_organization')

    # --- 2. Handle Spatial Fields ---
    spatial_field_names = get_dynamic_fields(model, SPATIAL_FIELD_TYPES)
    
    for field_name in spatial_field_names:
        dynamic_prefix_fields.append(field_name)

        # Assign the Searchable Leaflet Widget
        # Note: We must instantiate the widget class here.
        dynamic_widgets[field_name] = SPATIAL_WIDGET()

    # --- 3. Apply Dynamic Fields to Layout and Fields List ---
    dynamic_prefix_fields.reverse()

    for field_name in dynamic_prefix_fields:
        if field_name not in layout.fields:
            layout.fields.insert(0, field_name)

        if isinstance(fields, Sequence) and field_name not in fields:
            fields_list = list(fields)
            fields_list.insert(0, field_name)
            fields = tuple(fields_list)

    helper = FormHelper()
    helper.layout = layout
    helper.form_tag = form_tag

    # --- 4. Build the Meta class with the dynamic widgets ---
    Meta = type('Meta', (object,), {
        'model': model,
        'fields': fields or '__all__',
        'exclude': exclude,
        'widgets': dynamic_widgets
    })

    return type(
        form_class_name or f"{model._meta.object_name}ModelForm",
        (forms.ModelForm,),
        {'Meta': Meta, 'helper': helper, '__module__': model.__module__}
    )