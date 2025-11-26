from django.apps import apps
from django import template
from django.core.cache import cache
from django.utils.safestring import mark_safe
from django.template.loader import render_to_string
from django.core.exceptions import FieldDoesNotExist
from datetime import timedelta
import re
import qrcode
from io import BytesIO
import base64

# --- Constants ---
# Re-use the existing compiled regex for digits
digital_value = re.compile(r"^\d+$") 
register = template.Library()

# ====================================================================
# A. Filters
# ====================================================================

@register.filter('getattr')
def getattribute(value, arg):
    """
    Safely retrieve an attribute, dictionary key, or list index.
    """
    # 1. Standard attribute access (e.g., obj.field)
    if hasattr(value, str(arg)):
        return getattr(value, arg)
    
    # 2. Dictionary key access (e.g., dict['key'])
    elif hasattr(value, 'get'):
        return value.get(arg)
        
    # 3. List/Tuple index access (e.g., list[0])
    elif digital_value.match(str(arg)):
        try:
            index = int(arg)
            if 0 <= index < len(value):
                return value[index]
        except (TypeError, ValueError, IndexError):
            # Ignore if not indexable or if index is out of range
            pass
            
    return None

@register.filter('qs_to_values')
def qs_to_values(qs, field):
    """
    Converts a queryset to a list of dictionaries with specified fields.
    Handles potential AttributeError if qs isn't a QuerySet.
    """
    if hasattr(qs, 'values'):
        return list(qs.values(*field.split(',')))
    # Fallback to an empty list or return the original value for non-querysets
    return []

@register.filter('toint')
def toint(value):
    """
    Safely converts a value to an integer, returning 0 on failure.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0

@register.filter(name="addDays")
def addDays(date, days):
    """
    Adds a specified number of days to a date object.
    """
    if date and isinstance(days, int):
        return date + timedelta(days=days)
    return date

@register.filter(name='qs_sum_of')
def qs_sum_of(qs, field):
    """
    Calculates the sum of a specific field across all objects in a queryset/iterable.
    """
    # Use sum() on the QuerySet for database-level calculation (more efficient)
    if hasattr(qs, 'aggregate'):
        # Django's aggregation is highly recommended for efficiency
        from django.db.models import Sum
        try:
            return qs.aggregate(total=Sum(field))['total'] or 0
        except FieldDoesNotExist:
            pass # Fall back to python sum if aggregation fails or field is invalid
            
    # Fallback for non-QuerySets or failed aggregation
    return sum([getattr(obj, field, 0) for obj in qs])

@register.filter(name='qs_limit')
def qs_limit(qs, limit):
    """
    Limits the number of objects in a queryset/list.
    """
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        return qs # Return original if limit is not an integer
        
    if qs is None: return None
    return qs[:limit]

@register.filter(name="model_attr")
def get_model_fields(model, attr):
    """
    Retrieves an attribute from the model's _meta class.
    Alias of modelmeta for consistency.
    """
    return modelmeta(model, attr)

@register.filter
def get_obj_pk(qs, pk):
    """
    Filters a queryset to find an object by its primary key.
    """
    if hasattr(qs, 'filter'):
        return qs.filter(pk=pk).first()
    return None

@register.filter
def modelmeta(model, attr):
    """
    Retrieves an attribute from the model's _meta class.
    """
    if hasattr(model, '_meta'):
        return getattr(model._meta, attr, None)
    return None

@register.filter('cache_get')
def cache_get(key):
    """
    Simple wrapper for django.core.cache.cache.get.
    """
    return cache.get(key)


# ====================================================================
# B. Simple Tags
# ====================================================================

@register.simple_tag(takes_context=True)
def watermarker(context, message):
    """
    Renders a watermarker element using a dedicated template for safety.
    """
    context['watermark_message'] = message
    # Use render_to_string for safer HTML rendering
    return render_to_string('components/watermark.html', context.flatten())

# NOTE: The original qs_to_table is REMOVED due to the HIGH-RISK use of eval().
# If you need similar dynamic filtering, you must pass a safe dictionary object
# directly from the view/context, not a string for eval().

@register.simple_tag(name='table')
def render_table(qs, *args):
    """
    Renders an HTML table from a QuerySet using a dedicated template for safety.
    This replaces the unsafe raw HTML string construction.
    """
    if not qs or not args:
        return ''
        
    # Get model fields, filtering by the requested args
    model_fields = [
        field for field in qs.model._meta.fields 
        if field.name in args
    ]
    
    context = {
        'queryset': qs,
        'fields': model_fields,
        'field_names': args,
    }
    
    # Render the table using a dedicated template
    # The template 'components/render_table.html' must now be created.
    return render_to_string('components/render_table.html', context)