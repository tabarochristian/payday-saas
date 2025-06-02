# payroll/views/payslips.py

from django.shortcuts import render, get_object_or_404, redirect
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count, Sum
from django.urls import reverse_lazy
from django.db.models import Sum
from django.apps import apps
from django.contrib import messages
from payroll.filters import PayslipFilter
from core.forms.button import Button
from core.views import Change
import logging

logger = logging.getLogger(__name__)


class Payslips(Change):
    """
    A class-based view to handle bulk payslip operations in the payroll system.
    
    Features:
      - Filters by item code (positive/negative)
      - Pagination support
      - Custom action buttons (export, synthesis, print)
      - Dynamic field selection for display
    """
    template_name = "payroll/payslips.html"
    PAGINATION_COUNT = 100

    def get_model(self):
        """Returns the PaidEmployee model."""
        return apps.get_model("payroll", model_name="paidemployee")

    def dispatch(self, request, *args, **kwargs):
        """Validates user has view permission before allowing access."""
        model_class = self.get_model()
        view_perm = f"{model_class._meta.app_label}.view_{model_class._meta.model_name}"
        
        if not request.user.has_perm(view_perm):
            messages.warning(request, _("Vous n'avez pas la permission de voir cet objet."))
            return redirect(reverse_lazy("core:home"))

        self.next = request.GET.get("next")
        return super().dispatch(request, *args, **kwargs)

    def get_action_buttons(self, obj=None):
        """
        Generates dynamic action buttons including dropdowns for synthesis,
        listing, export, and print options.
        """
        logger.debug("Generating action buttons...")
        obj = obj or self._get_object()
        app = "payroll"
        model = "payslip"
        model_permission_prefix = f"{app}.{model}"

        paid_employee = apps.get_model('payroll', model_name='paidemployee')
        payment = paid_employee.objects.filter(payroll=obj).values("payment_method").annotate(
            count=Count("payment_method"),
            amount=Sum("net")
        )
        payment = payment[0] or []


        # Main buttons
        buttons = [
            Button(
                tag="button",
                text=_("Envoyer à la banque 🚀"),
                classes="btn btn-success dropdown-toggle",
                permission=f"{model_permission_prefix}.view",
                dropdown=[
                    Button(
                        tag="a",
                        text=_("EasyPay"),
                        url=reverse_lazy("core:create", kwargs={"app": "easypay", "model": "mobile"}) 
                        + f"?payroll={obj.pk}"
                        + f"&amount_total={payment["amount"] or 0}"
                        + f"&count={payment["count"] or 0}",
                        classes="dropdown-item",
                        permission=f"{model_permission_prefix}.view"
                    ),
                ]
            ),
            Button(
                tag="button",
                text=_("Synthèse"),
                classes="btn btn-light-warning dropdown-toggle",
                permission=f"{model_permission_prefix}.view",
                dropdown=[
                    Button(
                        tag="a",
                        text=_("Par somme"),
                        url=reverse_lazy("payroll:synthesis", args=["sum", obj.pk]),
                        classes="dropdown-item",
                        permission=f"{model_permission_prefix}.view"
                    ),
                    Button(
                        tag="a",
                        text=_("Par effectif"),
                        url=reverse_lazy("payroll:synthesis", args=["count", obj.pk]),
                        classes="dropdown-item",
                        permission=f"{model_permission_prefix}.view"
                    ),
                ]
            ),
            Button(
                tag="button",
                text=_("Listing"),
                classes="btn btn-light-info dropdown-toggle",
                permission=f"{model_permission_prefix}.view",
                dropdown=[
                    *[Button(
                        tag="a",
                        text=duty["name"],
                        url=reverse_lazy("payroll:listing", args=[obj.pk]) + f"?code={duty['code']}",
                        classes="dropdown-item",
                        permission=f"{model_permission_prefix}.view"
                    ) for duty in self.duties()],
                    *[Button(
                        tag="a",
                        text=item["name"],
                        url=reverse_lazy("payroll:listing", args=[obj.pk]) + f"?code={item['code']}",
                        classes="dropdown-item",
                        permission=f"{model_permission_prefix}.view"
                    ) for item in self.items()]
                ]
            ),
            Button(
                text=_("Exportateur"),
                tag="a",
                url=reverse_lazy("core:exporter", kwargs={"app": app, "model": "paidemployee"}) +
                     f"?payroll_id={obj.pk}",
                classes="btn btn-light-success",
                permission=f"{model_permission_prefix}.view"
            ),
            Button(
                text=_("Impr. les fiches de paie"),
                tag="button",
                classes="btn btn-success",
                permission=f"{model_permission_prefix}.view",
                attrs={
                    "onclick": (
                        "window.location.href = '{}?pk__in=' + getSelectedRows('table').join(',');"
                    ).format(reverse_lazy("payroll:slips")),
                    "title": _("Sélectionnez des lignes à imprimer")
                }
            )
        ]

        parent_buttons = super().get_action_buttons(obj)
        relevant_parent_buttons = [btn for btn in parent_buttons if "Sauvegarder" not in btn.text]
        get_extra_buttons = getattr(obj, "get_action_buttons", None)

        extra_buttons = []
        if callable(get_extra_buttons):
            result = get_extra_buttons()
            if isinstance(result, (list, tuple)):
                extra_buttons = [Button(**b) for b in result]
            elif result:
                extra_buttons = [Button(**result)]
        elif get_extra_buttons:
            if isinstance(get_extra_buttons, (list, tuple)):
                extra_buttons = [Button(**b) for b in get_extra_buttons]
            else:
                extra_buttons = [Button(**get_extra_buttons)]

        all_buttons = extra_buttons + relevant_parent_buttons + buttons
        return [btn for btn in all_buttons if self.request.user.has_perm(btn.permission)]

    def sheets(self):
        """Retrieves ModelSelect fields from Employee model for UI purposes."""
        try:
            employee_model = apps.get_model("employee", "Employee")
            select_fields = [
                field.name for field in employee_model._meta.fields
                if field.get_internal_type() == "ModelSelect"
            ]
            return [{"name": f"{f}__name", "verbose_name": employee_model._meta.get_field(f).verbose_name}
                    for f in select_fields]
        except Exception as e:
            logger.error(f"Error retrieving Employee model fields: {str(e)}", exc_info=True)
            return []

    def duties(self):
        """Retrieves negative-value items for Synthesis (e.g., deductions)."""
        try:
            ItemPaid = apps.get_model("payroll", "ItemPaid")
            return list(
                ItemPaid.objects.filter(employee__payroll=self.kwargs.get("pk"), amount_qp_employee__lte=0)
                .select_related("employee")
                .values("name", "code")
                .distinct()
            )
        except Exception as e:
            logger.error(f"Error retrieving duties: {str(e)}", exc_info=True)
            return []

    def items(self):
        """Retrieves positive-value items for Synthesis (e.g., bonuses, allowances)."""
        try:
            ItemPaid = apps.get_model("payroll", "ItemPaid")
            return list(
                ItemPaid.objects.filter(employee__payroll=self.kwargs.get("pk"), amount_qp_employee__gte=0)
                .select_related("employee")
                .values("name", "code")
                .distinct()
            )
        except Exception as e:
            logger.error(f"Error retrieving items: {str(e)}", exc_info=True)
            return []

    def get_list_display(self):
        """Returns sorted list of fields to display in the list."""
        try:
            model_class = apps.get_model("payroll", "paidemployee")
            list_display = ["registration_number", "last_name", "net", "payment_method"]
            order_map = {field: i for i, field in enumerate(list_display)}
            return sorted(
                [f for f in model_class._meta.fields if f.name in list_display],
                key=lambda f: order_map[f.name]
            )
        except Exception as e:
            logger.error(f"Error retrieving list display fields: {str(e)}", exc_info=True)
            return []

    def _get_query_params(self, request):
        """Extract valid query parameters for filtering."""
        return {k: v for k, v in request.GET.items() if v}

    def _filter_queryset(self, queryset, query):
        """Applies filters safely based on valid model fields."""
        try:
            valid_fields = [f.name for f in queryset.model._meta.fields]
            filter_params = {k: v for k, v in query.items() if k in valid_fields}
            return queryset.filter(**filter_params)
        except Exception as e:
            logger.error(f"Error applying filters: {str(e)}", exc_info=True)
            return queryset

    def get(self, request, pk):
        """
        Handles GET requests by loading filtered and paginated payslip data.
        """
        logger.info(f"User {request.user} requested payslips for Payroll ID={pk}")
        try:
            self.kwargs.update({"app": "payroll", "model": "payroll"})
            model_class = apps.get_model("payroll", "payroll")
            payroll_obj = get_object_or_404(model_class, id=pk)

            query_params = self._get_query_params(request)

            qs = payroll_obj.paidemployee_set.all().select_related("payroll").prefetch_related("employee")
            filter_set = PayslipFilter(query_params, queryset=qs)
            filtered_qs = self._filter_queryset(filter_set.qs, query_params)

            paginator = Paginator(filtered_qs, self.PAGINATION_COUNT)
            page_number = request.GET.get("page", 1)

            try:
                page_obj = paginator.page(page_number)
            except (EmptyPage, PageNotAnInteger):
                page_obj = paginator.page(1)

            overall_net = round(filtered_qs.aggregate(amount=Sum("net"))["amount"] or 0, 2)

            action_buttons = self.get_action_buttons(payroll_obj)
            sheets = self.sheets()
            list_display = self.get_list_display()

            logger.info(f"Loaded payslips for Payroll ID={pk}, count={filtered_qs.count()}")
            
            # ✅ Safe use of locals() for template rendering
            return render(request, self.template_name, locals())

        except Exception as e:
            logger.exception(f"GET request failed for Payroll ID={pk}: {str(e)}")
            messages.error(request, _("Une erreur est survenue lors du chargement des fiches de paie."))
            return redirect(self.next or reverse_lazy("core:home"))