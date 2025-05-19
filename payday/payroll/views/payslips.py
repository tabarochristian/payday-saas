```python
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.translation import gettext as _
from django.core.paginator import Paginator
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
    A class-based view to handle payslip-related operations in the payroll system.

    Displays payslip details for a payroll instance, with filtering, pagination,
    and custom action buttons (synthesis, listing, exporter, print payslips).
    
    Attributes:
        template_name (str): Template for rendering the payslip view.
        PAGINATION_COUNT (int): Number of items per page for pagination.
    """
    template_name = 'payroll/payslips.html'
    PAGINATION_COUNT = 100

    def get_model(self):
        """
        Returns the Payslip model.

        Returns:
            Model: The Payslip model from the payroll app.
        """
        return apps.get_model('payroll', model_name='payslip')

    def dispatch(self, request, *args, **kwargs):
        """
        Validates user permissions before processing the request.

        Args:
            request (HttpRequest): The incoming request.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            HttpResponse: Redirects to home if permission is lacking, else proceeds.
        """
        model_class = self.get_model()
        view_perm = f"{model_class._meta.app_label}.view_{model_class._meta.model_name}"

        if not request.user.has_perm(view_perm):
            messages.warning(request, _("Vous n'avez pas la permission de voir cet objet."))
            return redirect(reverse_lazy("core:home"))

        self.next = request.GET.get('next')
        return super().dispatch(request, *args, **kwargs)

    def get_action_buttons(self, obj=None):
        """
        Generates action buttons for the payslip view, including synthesis, listing,
        exporter, and print payslips buttons.

        Args:
            obj: Optional model instance (Payroll) for context-specific buttons.

        Returns:
            list: A list of Button objects filtered by user permissions.
        """
        obj = obj or self._get_object()
        app = 'payroll'
        model = 'payslip'
        model_permission_prefix = f"{app}.{model}"

        buttons = [
            Button(
                tag='button',
                text=_('Synthesis'),
                classes='btn btn-light-warning dropdown-toggle',
                permission=f"{model_permission_prefix}.view",
                dropdown=[
                    Button(
                        tag='a',
                        text=_('Par somme'),
                        url=reverse_lazy('payroll:synthesis', args=['sum', obj.pk]),
                        classes='dropdown-item',
                        permission=f"{model_permission_prefix}.view"
                    ),
                    Button(
                        tag='a',
                        text=_('Par effectif'),
                        url=reverse_lazy('payroll:synthesis', args=['count', obj.pk]),
                        classes='dropdown-item',
                        permission=f"{model_permission_prefix}.view"
                    ),
                ]
            ),
            Button(
                tag='button',
                text=_('Listing'),
                classes='btn btn-light-info dropdown-toggle',
                permission=f"{model_permission_prefix}.view",
                dropdown=[
                    *[Button(
                        tag='a',
                        text=duty['name'],
                        url=reverse_lazy('payroll:listing', args=[obj.pk]) + f"?code={duty['code']}",
                        classes='dropdown-item',
                        permission=f"{model_permission_prefix}.view"
                    ) for duty in self.duties()],
                    *[Button(
                        tag='a',
                        text=item['name'],
                        url=reverse_lazy('payroll:listing', args=[obj.pk]) + f"?code={item['code']}",
                        classes='dropdown-item',
                        permission=f"{model_permission_prefix}.view"
                    ) for item in self.items()]
                ]
            ),
            Button(
                text=_('Exportateur'),
                tag='a',
                url=reverse_lazy('core:exporter', kwargs={'app': app, 'model': 'paidemployee'}) + f'?payroll_id={obj.pk}',
                classes='btn btn-light-success',
                permission=f"{model_permission_prefix}.view"
            ),
            Button(
                text=_('Imprimer les fiches de paie'),
                tag='button',
                classes='btn btn-success',
                permission=f"{model_permission_prefix}.view",
                attrs={
                    'onclick': (
                        "window.location.href = '{}?pk__in=' + "
                        "getSelectedRows('table').join(',');"
                    ).format(reverse_lazy('payroll:slips'))
                }
            )
        ]

        # Handle model-specific extra buttons from parent
        parent_buttons = super().get_action_buttons(obj)
        # Only include parent buttons that are relevant (e.g., exclude Save if not needed)
        relevant_parent_buttons = [btn for btn in parent_buttons if 'Sauvegarder' not in btn.text]

        # Handle model-specific extra buttons
        get_action_buttons = getattr(obj, 'get_action_buttons', None)
        extra_buttons = [Button(**button) for button in get_action_buttons]

        # Combine and filter buttons by permission
        return [btn for btn in extra_buttons + relevant_parent_buttons + buttons if self.request.user.has_perm(btn.permission)]

    def sheets(self):
        """
        Retrieves fields from the Employee model that are of type 'ModelSelect'.

        Returns:
            list: A list of dictionaries containing field names (with '__name' appended)
                  and their verbose names.
        """
        try:
            employee_model = apps.get_model('employee', 'Employee')
            select_fields = [field for field in employee_model._meta.fields if field.get_internal_type() == 'ModelSelect']
            return [{'name': f"{field.name}__name", 'verbose_name': field.verbose_name} for field in select_fields]
        except Exception as e:
            logger.error(f"Error retrieving Employee model fields: {str(e)}")
            return []

    def duties(self):
        """
        Retrieves distinct duty items with non-positive employee quote part amounts.

        Returns:
            list: A list of dictionaries with 'name' and 'code' for duty items.
        """
        try:
            ItemPaid = apps.get_model('payroll', 'ItemPaid')
            return list(
                ItemPaid.objects.filter(employee__payroll=self.kwargs.get('pk'))
                .filter(amount_qp_employee__lte=0)
                .select_related('employee')
                .values('name', 'code')
                .distinct()
            )
        except Exception as e:
            logger.error(f"Error retrieving duties for payroll {self.kwargs.get('pk')}: {str(e)}")
            return []

    def items(self):
        """
        Retrieves distinct items with non-negative employee quote part amounts.

        Returns:
            list: A list of dictionaries with 'name' and 'code' for items.
        """
        try:
            ItemPaid = apps.get_model('payroll', 'ItemPaid')
            return list(
                ItemPaid.objects.filter(employee__payroll=self.kwargs.get('pk'))
                .filter(amount_qp_employee__gte=0)
                .select_related('employee')
                .values('name', 'code')
                .distinct()
            )
        except Exception as e:
            logger.error(f"Error retrieving items for payroll {self.kwargs.get('pk')}: {str(e)}")
            return []

    def get_list_display(self):
        """
        Defines fields to display in the payslip list view.

        Returns:
            list: A sorted list of field objects based on predefined ordering.
        """
        try:
            model_class = apps.get_model('payroll', 'paidemployee')
            list_display = ["registration_number", "last_name", "net"]
            list_display_order = {field: i for i, field in enumerate(list_display)}
            return sorted(
                [field for field in model_class._meta.fields if field.name in list_display],
                key=lambda field: list_display_order[field.name]
            )
        except Exception as e:
            logger.error(f"Error retrieving list display fields: {str(e)}")
            return []

    def get(self, request, pk):
        """
        Handles GET requests by retrieving payroll and paidemployee data, applying
        filters, paginating results, and rendering the payslips template.

        Args:
            request (HttpRequest): The incoming GET request.
            pk (int): The primary key of the payroll object.

        Returns:
            HttpResponse: The rendered payslips view.
        """
        try:
            self.kwargs.update({'app': 'payroll', 'model': 'payroll'})
            model_class = apps.get_model('payroll', 'payroll')
            payroll_obj = get_object_or_404(model_class, id=pk)

            # Get query parameters and filter queryset
            query_params = self._get_query_params(request)
            qs = payroll_obj.paidemployee_set.all().select_related('payroll').prefetch_related('employee')
            filter_set = PayslipFilter(query_params, queryset=qs)
            filtered_qs = self._filter_queryset(filter_set.qs, query_params)

            # Apply pagination
            paginator = Paginator(filtered_qs, self.PAGINATION_COUNT)
            page_number = request.GET.get('page', 1)
            page_obj = paginator.get_page(page_number)

            # Calculate overall net amount
            overall_net = round(filtered_qs.aggregate(amount=Sum('net'))['amount'] or 0, 2)

            # Get action buttons and other context
            action_buttons = self.get_action_buttons(payroll_obj)
            sheets = self.sheets()
            list_display = self.get_list_display()

            return render(request, self.template_name, locals())
        
        except Exception as e:
            logger.error(f"Error processing GET request for payroll {pk}: {str(e)}")
            messages.error(request, _("Une erreur est survenue lors du chargement des fiches de paie."))
            return redirect(self.next or reverse_lazy('core:home'))

    def _get_query_params(self, request):
        """
        Extracts query parameters from the request's GET data.

        Args:
            request (HttpRequest): The incoming request.

        Returns:
            dict: A dictionary of non-empty query parameters.
        """
        return {k: v for k, v in request.GET.items() if v}

    def _filter_queryset(self, queryset, query):
        """
        Filters the queryset using query parameters that correspond to model fields.

        Args:
            queryset (QuerySet): The original queryset to filter.
            query (dict): Dictionary of query parameters.

        Returns:
            QuerySet: The filtered queryset.
        """
        try:
            valid_fields = [field.name for field in queryset.model._meta.fields]
            filter_params = {k: v for k, v in query.items() if k in valid_fields}
            return queryset.filter(**filter_params)
        except Exception as e:
            logger.error(f"Error filtering queryset: {str(e)}")
            return queryset
```