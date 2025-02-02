from django.shortcuts import render, redirect, get_object_or_404
from django.utils.translation import gettext as _
from django.contrib import messages
from datetime import timedelta
from django.apps import apps

from core.forms.button import Button
from core.views import Change

# Defining constants for payroll status
PAYROLL_STATUSES = (
    "IN_PROGRESS",
    "COMPLETED",
    "ERROR"
)

class Preview(Change):
    template_name = 'payroll/preview.html'

    def get_action_buttons(self):
        kwargs = self.kwargs
        buttons = super().get_action_buttons()
        del buttons[len(buttons) - 2:len(buttons)]

        buttons.append(Button(
            tag='button',
            classes='btn btn-success',
            text=_('Commencer la paie'),
            permission=f'{kwargs["app"]}.change_{kwargs["model"]}',
            attrs={
                'type': 'submit',
                'form': f'form-{kwargs["model"]}',
                'name': 'status',
                'value': 'IN_PROGRESS',
            }
        ))

        return buttons

    def estimate_duration(self, qs, obj):
        item_model = apps.get_model('payroll', 'item')
        legal_item_model = apps.get_model('payroll', 'legalitem')

        items_count = item_model.objects.count() + legal_item_model.objects.count()

        return timedelta(milliseconds=items_count * qs.count() * 3)

    def get(self, request, pk):
        self.kwargs['app'] = 'payroll'
        self.kwargs['model'] = 'payroll'
        model = apps.get_model('payroll', 'payroll')
        obj = get_object_or_404(model, pk=pk)

        paid_employee_model = apps.get_model('payroll', 'paidemployee')
        qs = paid_employee_model.objects.filter(payroll=obj)

        if obj.status in PAYROLL_STATUSES:
            return redirect('payroll:payslips', pk=pk)

        estimation_duration = self.estimate_duration(qs, obj)
        return render(request, self.template_name, locals())

    def post(self, request, pk):
        self.kwargs['app'] = 'payroll'
        self.kwargs['model'] = 'payroll'
        model = apps.get_model('payroll', 'payroll')
        obj = get_object_or_404(model, pk=pk)

        data = request.POST.dict()
        status = data.get('status')
        if status and status in PAYROLL_STATUSES:
            messages.success(request, _('La paie a commencé'))
            obj.status = status
            obj.save()

        from payroll.tasks import Payer
        Payer().run(pk)

        return redirect('payroll:payslips', pk=pk)
