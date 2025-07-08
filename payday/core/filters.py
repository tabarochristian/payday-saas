from django.db.models import Q, CharField, TextField
from django.utils.translation import gettext as _
from core.forms import DateRangeWidget
from functools import reduce
from django import forms
import django_filters

class DateTimeRangeWidget(forms.MultiWidget):
    def __init__(self, attrs=None):
        widgets = [
            forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        ]
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if value:
            return [value.start, value.stop]
        return [None, None]


class AdvanceFilterSet(django_filters.FilterSet):
    q = django_filters.CharFilter(
        label=str, 
        method='search', 
        widget=forms.TextInput(attrs={'class': 'form-control d-none'})
    )
    
    def search(self, queryset, name, value):
        """
        Filters the queryset based on a search query applied to all CharField and TextField fields.
        """
        if not value.strip():
            return queryset
        
        model = self._meta.model
        fields = getattr(model, 'search_fields', [])
        
        # If no specific search fields are defined, use all CharField and TextField fields
        if not fields:
            fields = [field.name for field in model._meta.fields if isinstance(field, (CharField, TextField))]
        
        query = reduce(lambda q, field: q | Q(**{f"{field}__icontains": value}), fields, Q())
        return queryset.filter(query)

    def hard_filter(self):
        """
        Filters the queryset based on hard filters (all valid field filters in the request data).
        """
        # Extracting non-empty query parameters
        query_params = {k: v for k, v in self.data.items() if v}
        valid_fields = {field.name for field in self._meta.model._meta.fields}

        # Filtering parameters that correspond to valid fields
        filter_params = {
            k: v for k, v in query_params.items() if k.split("__")[0] in valid_fields
        }
        
        return self.queryset.filter(**filter_params)


def filter_set_factory(_model, fields):
    """
    Factory function to dynamically create a Django FilterSet class for a given model and filter fields.
    Supports DateField and DateTimeField with proper range widgets.
    """
    attrs = {}
    _fields = fields

    class Meta:
        model = _model
        fields = _fields

    for field_name in fields:
        # Split '__' if filter lookup is used (e.g. 'created__gte')
        field_base_name = field_name.split('__')[0]

        try:
            model_field = _model._meta.get_field(field_base_name)
        except Exception:
            continue  # Skip if field is not found in model

        internal_type = model_field.get_internal_type()

        if internal_type == 'DateField':
            attrs[field_name] = django_filters.DateFromToRangeFilter(widget=DateRangeWidget())
        elif internal_type == 'DateTimeField':
            attrs[field_name] = django_filters.DateTimeFromToRangeFilter(widget=DateTimeRangeWidget())

    attrs['Meta'] = Meta
    return type(f"{_model._meta.object_name}FilterSet", (AdvanceFilterSet,), attrs)
