from django.shortcuts import render, get_object_or_404
from django.utils.translation import gettext as _
from django.core.paginator import Paginator
from django.urls import reverse_lazy
from django.db.models import Sum
from django.apps import apps

from payroll.filters import PayslipFilter
from core.forms.button import Button
from core.views import Change


class Payslips(Change):
    """A class-based view for handling payslip operations in the payroll system."""

    template_name = 'payroll/payslips.html'
    PAGINATION_COUNT = 100

    def get_action_buttons(self):
        """Generate and return the action buttons for the view."""
        pk = self.kwargs['pk']
        app, model = 'payroll', 'payslip'
        
        buttons = super().get_action_buttons()
        del buttons[len(buttons) - 1:len(buttons)]
        buttons += [
            Button(
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
            ),
            Button(
                tag='button',
                text=_('Listing'),
                classes='btn btn-light-info dropdown-toggle',
                permission=f'{app}.view_{model}',
                dropdown=[
                    Button(
                        tag='a',
                        text=duty['name'],
                        url=reverse_lazy('payroll:listing', args=[pk])+f"?code={duty['code']}",
                        classes='dropdown-item',
                    ) for duty in self.duties()
                ] + [
                    Button(
                        tag='a',
                        text=item['name'],
                        url=reverse_lazy('payroll:listing', args=[pk])+f"?code={item['code']}",
                        classes='dropdown-item',
                    ) for item in self.items()
                ]
            ),
            Button(
                text=_('Exportateur'),
                tag='a',
                url=reverse_lazy('core:exporter', kwargs={
                    'app': app, 
                    'model': 'paidemployee',
                }) + f'?payroll_id={pk}',
                classes='btn btn-light-success',
                permission=f'{app}.view_{model}'
            )
        ]
        del buttons[0]
        return buttons

    def sheets(self):
        """Get a list of fields related to the employee model for displaying in sheets."""
        employee = apps.get_model('employee', 'Employee')
        data = [field for field in employee._meta.fields if field.get_internal_type() == 'ModelSelect']
        return [{'name': field.name+'__name', 'verbose_name': field.verbose_name} for field in data]

    def duties(self):
        """Get a list of duties with amounts less than or equal to zero."""
        ItemPaid = apps.get_model('payroll', 'ItemPaid')
        return ItemPaid.objects.filter(employee__payroll=self.kwargs['pk'])\
            .filter(amount_qp_employee__lte=0).values('name', 'code').distinct()

    def items(self):
        """Get a list of items with amounts greater than or equal to zero."""
        ItemPaid = apps.get_model('payroll', 'ItemPaid')
        return list(ItemPaid.objects.filter(employee__payroll=self.kwargs['pk'])\
            .filter(amount_qp_employee__gte=0).values('name', 'code').distinct())

    def get(self, request, pk):
        """Handle GET requests and return the payslip details."""
        self.kwargs['app'], self.kwargs['model'] = 'payroll', 'payroll'
        model = apps.get_model('payroll', 'payroll')

        obj = get_object_or_404(model, id=pk)
        query = self._get_query_params(request)
        qs = obj.paidemployee_set.all().select_related().prefetch_related()

        filter = PayslipFilter(query, queryset=qs)
        qs = self._filter_queryset(filter.qs, query)
        overall_net = round(qs.aggregate(amount=Sum('net'))['amount'] or 0, 2)

        #paginator = Paginator(qs.order_by(f'-{Payslip._meta.pk.name}'), self.PAGINATION_COUNT)
        #qs = paginator.page(int(request.GET.get('page', 1)))
        
        return render(request, self.template_name, locals())

    def _get_query_params(self, request):
        """Extract and return query parameters from the request."""
        return {k: v for k, v in request.GET.items() if v}

    def _filter_queryset(self, qs, query):
        """Filter the queryset based on the provided query parameters."""
        fields = [field.name for field in qs.model._meta.fields]
        return qs.filter(**{k: v for k, v in query.items() if k in fields})
