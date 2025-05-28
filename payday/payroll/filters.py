# payroll/filters.py or wherever appropriate

from django.utils.translation import gettext_lazy as _
from django_filters import FilterSet, CharFilter, ChoiceFilter
from employee.models import Branch, Grade, Status
from django.db.models import Q
from django import forms


class PayslipFilter(FilterSet):
    """
    A dynamic filter set for Payslip with support for branch, grade, and status.
    Uses lazy loading to prevent import errors and supports i18n.
    """

    # === Dynamic choice filters using lazy-loaded models ===
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set choices dynamically to avoid empty values at startup
        self.filters['status'].extra['choices'] = self._get_choices(Status)
        self.filters['branch'].extra['choices'] = self._get_choices(Branch)
        self.filters['grade'].extra['choices'] = self._get_choices(Grade)

    def _get_choices(self, model):
        """Helper to safely generate choices for dropdowns"""
        try:
            return [("", "---------")] + list(model.objects.values_list("name", "name").distinct())
        except Exception:
            return [("", "---------")]

    # === Filters ===
    status = ChoiceFilter(
        method="filter_by_status",
        label=_("Statut"),
        empty_label=_("Tous les statuts"),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    branch = ChoiceFilter(
        method="filter_by_branch",
        label=_("Site"),
        empty_label=_("Tous les sites"),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    grade = ChoiceFilter(
        method="filter_by_grade",
        label=_("Grade"),
        empty_label=_("Tous les grades"),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    payment_method = ChoiceFilter(
        label=_("Methode de paiements"),
        method="filter_by_payment_method",
        empty_label=_("Tous les methodes de paiements"),
        widget=forms.Select(attrs={"class": "form-control"}),
        choices=[("BANK", "Bank"), ("CASH", "Cash"), ("MOBILE MONEY", "Mobile Money")],
    )

    q = CharFilter(
        label=_("Recherche"),
        method="global_search",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": _("Rechercher...")}),
    )

    class Meta:
        fields = ("branch", "grade", "status")

    def global_search(self, queryset, name, value):
        """Search across multiple fields: registration number, name, etc."""
        if not value:
            return queryset

        search_fields = [
            'employee__registration_number',
            'employee__first_name',
            'employee__last_name'
        ]
        query = Q()
        for field in search_fields:
            query |= Q(**{f"{field}__icontains": value})

        return queryset.filter(query).distinct()

    def filter_by_branch(self, queryset, name, value):
        """Filter by employee's branch name"""
        if not value:
            return queryset
        return queryset.filter(employee__branch__name=value)

    def filter_by_grade(self, queryset, name, value):
        """Filter by employee's grade name"""
        if not value:
            return queryset
        return queryset.filter(employee__grade__name=value)

    def filter_by_status(self, queryset, name, value):
        """Filter by employee's status name"""
        if not value:
            return queryset
        return queryset.filter(employee__status__name=value)

    def filter_by_payment_method(self, queryset, name, value):
        """Filter by employee's status name"""
        if not value:
            return queryset
        return queryset.filter(employee__payment_method=value)