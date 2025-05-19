from django.shortcuts import render, get_object_or_404, redirect
from django.utils.translation import gettext as _
from django.core.paginator import Paginator
from django.urls import reverse_lazy
from django.db.models import Sum
from django.apps import apps

from payroll.filters import PayslipFilter
from core.forms.button import Button
from core.views import Change


class Payslips(Change):
    """
    A class-based view to handle payslip-related operations in the payroll system.

    This view displays payslip details for a payroll instance, along with filtering
    and export options. It prepares action buttons (e.g., synthesis, listing, exporter)
    and provides helper methods to fetch configuration data such as duty and item summaries.
    
    Attributes:
        template_name (str): The template used for rendering the payslip view.
        PAGINATION_COUNT (int): Number of items per page (currently unused).
    """
    template_name = 'payroll/payslips.html'
    PAGINATION_COUNT = 100

    def get_model(self):
        return apps.get_model('payroll', model_name='payslip')

    def get_action_buttons(self):
        """
        Generate the list of action buttons for the payslip view.

        This method removes unwanted buttons from the parent action buttons list
        and adds custom buttons for synthesis, listing, and exporting payroll data.

        Returns:
            list: A list of Button objects for the view.
        """
        pk = self.kwargs.get('pk')
        app = 'payroll'
        model = 'payslip'
        
        # Get the base action buttons defined in the parent view.
        buttons = super().get_action_buttons()
        # Remove the last button (or more) as desired.
        del buttons[-1:]
        # Create a synthesis dropdown button.
        synthesis_button = Button(
            tag='button',
            text=_('Synthesis'),
            classes='btn btn-light-warning dropdown-toggle',
            permission=f'{app}.view_{model}',
            dropdown=[
                Button(
                    tag='a',
                    text=_('Par somme'),
                    url=reverse_lazy('payroll:synthesis', args=['sum', pk]),
                    classes='dropdown-item',
                ),
                Button(
                    tag='a',
                    text=_('Par effectif'),
                    url=reverse_lazy('payroll:synthesis', args=['count', pk]),
                    classes='dropdown-item',
                ),
            ]
        )
        # Create a listing dropdown button using duties and items from helper methods.
        listing_button = Button(
            tag='button',
            text=_('Listing'),
            classes='btn btn-light-info dropdown-toggle',
            permission=f'{app}.view_{model}',
            dropdown=[
                # Button for each duty whose amounts are less than or equal to zero.
                *[Button(
                    tag='a',
                    text=duty['name'],
                    url=reverse_lazy('payroll:listing', args=[pk]) + f"?code={duty['code']}",
                    classes='dropdown-item',
                ) for duty in self.duties()],
                # Button for each item whose amounts are greater than or equal to zero.
                *[Button(
                    tag='a',
                    text=item['name'],
                    url=reverse_lazy('payroll:listing', args=[pk]) + f"?code={item['code']}",
                    classes='dropdown-item',
                ) for item in self.items()],
            ]
        )
        # Create an exporter button.
        exporter_button = Button(
            text=_('Exportateur'),
            tag='a',
            url=reverse_lazy('core:exporter', kwargs={'app': app, 'model': 'paidemployee'}) + f'?payroll_id={pk}',
            classes='btn btn-light-success',
            permission=f'{app}.view_{model}'
        )

        # Print payslips
        print_payslips_button = Button(
            text=_('Imprimer les fiches de paie'),
            tag='button',
            classes='btn btn-success',
            permission=f'{app}.view_{model}',
            attrs={
                'onclick': (
                    "window.location.href = '{}?pk__in=' + "
                    "getSelectedRows('table').join(',');"
                ).format(reverse_lazy('payroll:slips'))
            }
        )

        # Add the custom buttons, remove the first button from the inherited list.
        buttons = buttons[1:] + [synthesis_button, listing_button, exporter_button, print_payslips_button]
        # Return buttons filtered by user permission.
        return [button for button in buttons if self.request.user.has_perm(button.permission)]

    def sheets(self):
        """
        Retrieve a list of fields for the Employee model that are represented as 'ModelSelect'.
        
        Returns:
            list: A list of dictionaries containing the field name (appended with '__name')
                  and the field's verbose name.
        """
        employee_model = apps.get_model('employee', 'Employee')
        select_fields = [field for field in employee_model._meta.fields if field.get_internal_type() == 'ModelSelect']
        return [{'name': f"{field.name}__name", 'verbose_name': field.verbose_name} for field in select_fields]

    def duties(self):
        """
        Retrieve a list of duty items that have non-positive employee quote part amounts.
        
        Returns:
            QuerySet: A distinct queryset of duty items with fields 'name' and 'code'.
        """
        ItemPaid = apps.get_model('payroll', 'ItemPaid')
        return ItemPaid.objects.filter(employee__payroll=self.kwargs.get('pk')) \
            .filter(amount_qp_employee__lte=0).values('name', 'code').distinct()

    def items(self):
        """
        Retrieve a list of items with non-negative employee quote part amounts.
        
        Returns:
            list: A list of dictionaries with item 'name' and 'code'.
        """
        ItemPaid = apps.get_model('payroll', 'ItemPaid')
        return list(
            ItemPaid.objects.filter(employee__payroll=self.kwargs.get('pk')) \
            .filter(amount_qp_employee__gte=0).values('name', 'code').distinct()
        )

    def get_list_display(self):
        """
        Define the fields to display in the notifications list view.

        Returns:
            list: A sorted list of field objects, based on a predefined ordering.
        """
        model_class = apps.get_model('payroll', 'paidemployee')
        list_display = ["registration_number", "last_name", "net"]
        list_display_order = {field: i for i, field in enumerate(list_display)}
        # Filter the model's fields to include only those specified in "list_display" and sort them.
        return sorted(
            [field for field in model_class._meta.fields if field.name in list_display],
            key=lambda field: list_display_order[field.name]
        )

    def get(self, request, pk):
        """
        Handle GET requests by retrieving payroll and paidemployee data, filtering
        it according to provided query parameters, and rendering the payslips template.

        Args:
            request (HttpRequest): The incoming GET request.
            pk (int): The primary key of the payroll object.

        Returns:
            HttpResponse: The rendered payslips view.
        """
        # Set URL parameters for the payroll app/model.
        self.kwargs.update({'app': 'payroll', 'model': 'payroll'})
        model_class = apps.get_model('payroll', 'payroll')
        app = 'payroll'

        # Retrieve the payroll object.
        payroll_obj = get_object_or_404(model_class, id=pk)
        # Extract query parameters from the request.
        query_params = self._get_query_params(request)
        # Retrieve the paidemployee queryset related to the payroll.
        qs = payroll_obj.paidemployee_set.all().select_related().prefetch_related()

        # Apply additional filtering using the PayslipFilter.
        filter_set = PayslipFilter(query_params, queryset=qs)
        qs = self._filter_queryset(filter_set.qs, query_params)
        overall_net = round(qs.aggregate(amount=Sum('net'))['amount'] or 0, 2)

        return render(request, self.template_name, locals())

    def _get_query_params(self, request):
        """
        Extracts and returns query parameters from the request's GET data.

        Args:
            request (HttpRequest): The incoming request.

        Returns:
            dict: A dictionary of query parameters with non-empty values.
        """
        return {k: v for k, v in request.GET.items() if v}

    def _filter_queryset(self, queryset, query):
        """
        Filter the given queryset using only query parameters corresponding to the model's fields.

        Args:
            queryset (QuerySet): The original queryset to filter.
            query (dict): Dictionary of query parameters.

        Returns:
            QuerySet: The filtered queryset.
        """
        valid_fields = [field.name for field in queryset.model._meta.fields]
        filter_params = {k: v for k, v in query.items() if k in valid_fields}
        return queryset.filter(**filter_params)
