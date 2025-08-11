from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils.translation import gettext_lazy as _
from django.shortcuts import render, redirect
from payroll.filters import PayslipFilter
from django.urls import reverse_lazy
from core.forms.button import Button
from django.contrib import messages
from django.apps import apps
from core.views import Read
import logging

logger = logging.getLogger(__name__)

class Payslips(Read):
    """
    Handles bulk payslip operations with filtering, pagination, and custom actions.
    """
    template_name = "payroll/payslips.html"
    PAGINATION_COUNT = 1000
    
    @property
    def model_class(self):
        """Return the model class from URL kwargs."""
        return apps.get_model("payroll", model_name="payroll")

    def dispatch(self, request, *args, **kwargs):
        self.next = request.GET.get("next")
        return super().dispatch(request, *args, **kwargs)

    def get_action_buttons(self, obj=None):
        obj = obj or self._get_object()
        app, model = "payroll", "payslip"

        buttons = [
            Button(
                tag="button",
                text=_("Synthèse"),
                classes="btn btn-light-warning dropdown-toggle",
                permission=f"{app}.view_{model}",
                dropdown=[
                    Button(tag="a", text=_("Par somme"), url=reverse_lazy("payroll:synthesis", args=["sum", obj.pk]), classes="dropdown-item", permission=f"{app}.view_{model}"),
                    Button(tag="a", text=_("Par effectif"), url=reverse_lazy("payroll:synthesis", args=["count", obj.pk]), classes="dropdown-item", permission=f"{app}.view_{model}"),
                ]
            ),
            Button(
                tag="button",
                text=_("Listing"),
                classes="btn btn-light-info dropdown-toggle",
                permission=f"{app}.view_{model}",
                dropdown=[
                    *(Button(tag="a", text=duty["name"], url=reverse_lazy("payroll:listing", args=[obj.pk]) + f"?code={duty['code']}", classes="dropdown-item", permission=f"{app}.view_{model}") for duty in self.duties()),
                    *(Button(tag="a", text=item["name"], url=reverse_lazy("payroll:listing", args=[obj.pk]) + f"?code={item['code']}", classes="dropdown-item", permission=f"{app}.view_{model}") for item in self.items())
                ]
            ),
            Button(
                tag="a",
                text=_("Exportateur"),
                url=reverse_lazy("payroll:exporter", kwargs={"pk": obj.pk}),
                classes="btn btn-light-success",
                permission=f"{app}.view_{model}"
            ),
            Button(
                tag="button",
                text=_("Impr. les fiches de paie"),
                classes="btn btn-success",
                permission=f"{app}.view_{model}",
                attrs={
                    "onclick": f"window.location.href = '{reverse_lazy('payroll:slips')}?pk__in=' + getSelectedRows('table').join(',');",
                    "title": _("Sélectionnez des lignes à imprimer")
                }
            ),
            Button(
                tag='a',
                text=_('Supprimer'),
                classes='btn btn-light-danger',
                permission=f"{app}.view_{model}",
                url=reverse_lazy('core:delete', kwargs={
                    'model': self.kwargs['model'],
                    'app': self.kwargs['app'],
                }) + f'?pk__in={self.kwargs['pk']}'
            )
        ]

        parent_buttons = super().get_action_buttons(obj)
        return [btn for btn in buttons + parent_buttons if self.request.user.has_perm(btn.permission)]

    def sheets(self):
        try:
            employee_model = apps.get_model("employee", "Employee")
            return [
                {"name": f"{field.name}__name", "verbose_name": field.verbose_name}
                for field in employee_model._meta.fields
                if field.get_internal_type() == "ModelSelect"
            ]
        except Exception as e:
            logger.error(f"Error retrieving Employee model fields: {str(e)}")
            return []

    def duties(self):
        try:
            ItemPaid = apps.get_model("payroll", "ItemPaid")
            return list(ItemPaid.objects.filter(employee__payroll=self.kwargs.get("pk"), amount_qp_employee__lte=0)
                       .select_related("employee")
                       .values("name", "code")
                       .distinct())
        except Exception as e:
            logger.error(f"Error retrieving duties: {str(e)}")
            return []

    def items(self):
        try:
            ItemPaid = apps.get_model("payroll", "ItemPaid")
            return list(ItemPaid.objects.filter(employee__payroll=self.kwargs.get("pk"), amount_qp_employee__gte=0)
                       .select_related("employee")
                       .values("name", "code")
                       .distinct())
        except Exception as e:
            logger.error(f"Error retrieving items: {str(e)}")
            return []

    def get_list_display(self):
        try:
            model_class = apps.get_model("payroll", "PaidEmployee")
            list_display = ["registration_number", "last_name", "net", "payment_method"]
            return [field for field in model_class._meta.fields if field.name in list_display]
        except Exception as e:
            logger.error(f"Error retrieving list display fields: {str(e)}")
            return []

    def get(self, request, pk):
        logger.info(f"User {request.user} requested payslips for Payroll ID={pk}")
        try:
            # Update kwargs for parent class
            app, model = "payroll", "payroll"
            self.kwargs.update({"app": app, "model": model})
            model_class = self.model_class
            
            # Get payroll object
            obj = self._get_object()
            
            # Filter and paginate (Change the model to paidemployee to fetch the queryset)
            qs = self.get_queryset(
                model_class=apps.get_model(app, model_name="paidemployee")
            ).filter(
                payroll=obj
            ).select_related("payroll").prefetch_related("employee")

            filter_set = PayslipFilter(request.GET, queryset=qs)
            self.count = qs.count()
            
            try:
                paginator = Paginator(filter_set.qs, self.PAGINATION_COUNT)
                page_obj = paginator.page(request.GET.get("page", 1))
            except (EmptyPage, PageNotAnInteger):
                page_obj = paginator.page(1)

            # Call parent get method
            action_buttons = self.get_action_buttons(obj)
            return render(request, self.get_template_name(), locals())
            
        except Exception as e:
            logger.error(f"GET request failed for Payroll ID={pk}: {str(e)}")
            messages.error(request, _("Une erreur est survenue lors du chargement des fiches de paie."))
            return redirect(self.next or reverse_lazy("core:home"))