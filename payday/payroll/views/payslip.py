from django.shortcuts import render, get_object_or_404, redirect
from django.utils.translation import gettext as _
from core.forms import modelform_factory
from django.contrib import messages
from core.views import Change
from payroll import models

from core.models import Base
from django.apps import apps

from django.forms import CheckboxInput
from core.forms.button import Button

from django.urls import reverse_lazy

class Payslip(Change):
    template_name = "payroll/payslip.html"

    def get_action_buttons(self):
        """Generate and return the action buttons for the view."""
        pk = self.kwargs['pk']
        app, model = 'payroll', 'payslip'
        
        buttons = super().get_action_buttons()
        del buttons[len(buttons) - 2:len(buttons)]
        buttons += [
            Button(**{
                'tag': 'a',
                'text': _('Bulletin de paie'),
                'url': reverse_lazy('payroll:slips') + f"?id={pk}",
                'classes': 'btn btn-light-primary',
            })
        ]
        return buttons

    def get(self, request, pk):
        app, model = 'payroll', 'paidemployee'
        self.kwargs['app'] = app
        self.kwargs['model'] = model

        model = apps.get_model(app, model)
        obj = get_object_or_404(model, pk=pk)
        items = obj.itempaid_set.all().order_by('code')
        form = modelform_factory(models.ItemPaid, fields='__all__')

        form = form()
        return render(request, self.template_name, locals())
    
    def post(self, request, pk):
        app, model = 'payroll', 'paidemployee'

        self.kwargs['app'] = app
        self.kwargs['model'] = model

        model = apps.get_model(app, model)
        obj = get_object_or_404(model, pk=pk)

        base_fields = [field.name for field in Base._meta.fields] + ['id', 'payslip', 'rate', 'time']
        fields = [field.name for field in models.ItemPaid._meta.fields if field.name not in base_fields]

        form = modelform_factory(models.ItemPaid, fields='__all__')
        form = form(request.POST)

        if not form.is_valid():
            messages.add_message(request, messages.WARNING, message=_(f'Remplissez correctement le formulaire'))
            return render(request, self.template_name, locals())

        instance = form.save(commit=False)

        instance.amount_qp_employee = abs(instance.amount_qp_employee) * instance.type_of_item
        instance.amount_qp_employer = abs(instance.amount_qp_employer)
        instance.employee = obj

        instance.social_security_amount = abs(instance.social_security_amount) * instance.type_of_item
        instance.taxable_amount = abs(instance.taxable_amount) * instance.type_of_item

        instance.is_payable = True
        instance.is_bonus = False
        instance.save()

        obj.update()
        obj.payroll.update()

        messages.add_message(request, messages.SUCCESS, message=_(f'L\'element a été ajouté avec succès'))
        return redirect(request.META.get('HTTP_REFERER'))