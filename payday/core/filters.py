from django.utils.translation import gettext as _
from core.forms import DateRangeWidget
from django.db.models import Q, Field
from functools import lru_cache

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
        label="Search",
        method="search",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    # ---------------------------------------------------------
    # SEARCH HANDLER
    # ---------------------------------------------------------
    def search(self, queryset, name, value):
        value = value.strip()
        if not value:
            return queryset

        fields = self._get_all_icontains_fields()

        if not fields:
            return queryset

        q_obj = Q()
        for field in fields:
            q_obj |= Q(**{f"{field}__icontains": value})

        return queryset.filter(q_obj)

    # ---------------------------------------------------------
    # DISCOVER ALL FIELDS COMPATIBLE WITH __icontains
    # ---------------------------------------------------------
    @lru_cache(maxsize=128)
    def _get_all_icontains_fields(self):
        """
        Recursively collects ALL fields (local + related)
        that support the __icontains lookup.
        """
        model = self._meta.model
        return self._collect_icontains_fields(model)

    def _collect_icontains_fields(self, model, prefix="", visited=None):
        """
        Recursively walk through model relationships and collect
        any field that supports the __icontains lookup.
        """
        if visited is None:
            visited = set()

        # Prevent infinite loops in cyclic relations
        if model in visited:
            return []
        visited.add(model)

        searchable = []

        for field in model._meta.get_fields():
            path = f"{prefix}{field.name}"

            # -----------------------
            # 1. DIRECT FIELDS
            # -----------------------
            if not field.is_relation:
                if self._supports_icontains(field):
                    searchable.append(path)
                continue

            # -----------------------
            # 2. RELATION FIELDS
            # -----------------------
            if field.related_model and hasattr(field.related_model, "_meta"):
                # For ForeignKey, OneToOne, M2M, reverse relations
                rel_model = field.related_model

                # Recursively inspect related model
                searchable += self._collect_icontains_fields(
                    rel_model,
                    prefix=f"{path}__",
                    visited=visited
                )

        return searchable

    # ---------------------------------------------------------
    # DETECT IF FIELD SUPPORTS __icontains
    # ---------------------------------------------------------
    def _supports_icontains(self, field: Field):
        """
        A robust check if the field accepts __icontains.
        We test the registered lookups of the field instance.
        """
        return "__icontains" in field.get_lookups()

    # ---------------------------------------------------------
    # HARD FILTER
    # ---------------------------------------------------------
    def hard_filter(self):
        params = {k: v for k, v in self.data.items() if v not in ("", None)}

        # All valid base fields (allow lookups like field__gte, __lte)
        valid_bases = {f.name for f in self._meta.model._meta.get_fields()
                       if not f.is_relation or f.many_to_one or f.one_to_one}

        valid_filters = {
            k: v
            for k, v in params.items()
            if k.split("__")[0] in valid_bases
        }

        return self.queryset.filter(**valid_filters)


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
