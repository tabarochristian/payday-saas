from django.utils.translation import gettext as _
from core.forms import DateRangeWidget
from django.db.models import Q, Field
from functools import lru_cache

from django import forms
import django_filters


# ======================================================================
# DATETIME RANGE WIDGET
# ======================================================================
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


# ======================================================================
# ADVANCED FILTER SET
# ======================================================================
class AdvanceFilterSet(django_filters.FilterSet):

    q = django_filters.CharFilter(
        label="Search",
        method="search",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    # ------------------------------------------------------------------
    # SEARCH METHOD
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # FIND ALL FIELDS THAT SUPPORT icontains
    # ------------------------------------------------------------------
    @lru_cache(maxsize=128)
    def _get_all_icontains_fields(self):
        model = self._meta.model
        return self._collect_icontains_fields(model)

    # ------------------------------------------------------------------
    # RECURSIVE FIELD DISCOVERY
    # ------------------------------------------------------------------
    def _collect_icontains_fields(self, model, prefix="", visited=None):
        if visited is None:
            visited = set()

        if model in visited:
            return []
        visited.add(model)

        searchable = []

        for field in model._meta.get_fields():

            # Skip reverse relations and auto-created relations that don't map to DB fields
            if field.auto_created and not field.concrete:
                continue

            path = f"{prefix}{field.name}"

            # ----------------------------------------------------------
            # DIRECT FIELDS
            # ----------------------------------------------------------
            if not field.is_relation:
                if self._supports_icontains(field):
                    searchable.append(path)
                continue

            # ----------------------------------------------------------
            # RELATION FIELDS (ForeignKey, O2O, M2M)
            # ----------------------------------------------------------
            rel_model = getattr(field, "related_model", None)
            if not rel_model or not hasattr(rel_model, "_meta"):
                continue

            # Avoid overly deep recursive scans (safety)
            searchable += self._collect_icontains_fields(
                rel_model,
                prefix=f"{path}__",
                visited=visited
            )

        return searchable

    # ------------------------------------------------------------------
    # CHECK IF FIELD SUPPORTS LOOKUP
    # ------------------------------------------------------------------
    def _supports_icontains(self, field: Field):
        """
        Django lookup names DO NOT include the leading "__".
        get_lookups() keys -> "icontains", NOT "__icontains".
        """
        return "icontains" in field.get_lookups()

    # ------------------------------------------------------------------
    # HARD FILTER
    # ------------------------------------------------------------------
    def hard_filter(self):
        params = {k: v for k, v in self.data.items() if v not in ("", None)}

        valid_bases = {
            f.name
            for f in self._meta.model._meta.get_fields()
            if not f.is_relation or f.many_to_one or f.one_to_one
        }

        valid_filters = {
            k: v
            for k, v in params.items()
            if k.split("__")[0] in valid_bases
        }

        return self.queryset.filter(**valid_filters)


# ======================================================================
# FILTERSET FACTORY
# ======================================================================
def filter_set_factory(_model, fields):
    """
    Dynamically create a FilterSet for a given model.
    Adds proper widgets for DateField and DateTimeField.
    """

    attrs = {}
    _fields = fields

    class Meta:
        model = _model
        fields = _fields

    for field_name in fields:

        field_base_name = field_name.split("__")[0]

        try:
            model_field = _model._meta.get_field(field_base_name)
        except Exception:
            continue

        internal_type = model_field.get_internal_type()

        if internal_type == "DateField":
            attrs[field_name] = django_filters.DateFromToRangeFilter(
                widget=DateRangeWidget()
            )
        elif internal_type == "DateTimeField":
            attrs[field_name] = django_filters.DateTimeFromToRangeFilter(
                widget=DateTimeRangeWidget()
            )

    attrs["Meta"] = Meta
    return type(f"{_model._meta.object_name}FilterSet", (AdvanceFilterSet,), attrs)
