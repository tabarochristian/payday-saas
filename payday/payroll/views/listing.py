from django.shortcuts import render, redirect, get_object_or_404
from core.views import BaseView
from payroll.models import *
import pandas as pd

from django.urls import reverse_lazy
from django.contrib import messages
from django.apps import apps

intcomma = lambda value: "{:,}".format(round(abs(value), 2))

class Listing(BaseView):
    def get(self, request, pk):
        qs = []
        Payroll = apps.get_model('payroll', 'payroll')
        ItemPaid = apps.get_model('payroll', 'itempaid')

        query = request.GET.dict()
        obj = get_object_or_404(Payroll, id=pk)
        
        code = query.pop('code')
        item = Item.objects.filter(code=code).first()
        item = item or LegalItem.objects.filter(code=code).first()

        if not code: 
            messages.warning(request, 'Item not found.')
            return redirect(reverse_lazy('payroll:payslips', kwargs={'pk': obj.pk}))

        # .filter(**{f'payslip__employee__{k}__name':v for k,v in query.items()}) \
        qs = ItemPaid.objects.filter(code=code, employee__payroll=obj).all() \
            .values('employee__registration_number', 'employee__last_name', 'employee__middle_name', 'amount_qp_employee', 'amount_qp_employer')
        
        df = pd.DataFrame(qs)

        # Calculate the sums
        sum_amount_qp_employee = df['amount_qp_employee'].sum()
        sum_amount_qp_employer = df['amount_qp_employer'].sum()

        total_df = pd.DataFrame({
            'employee__registration_number': ['Total'],
            'employee__last_name': [''],
            'employee__middle_name': [''],
            'amount_qp_employee': [sum_amount_qp_employee],
            'amount_qp_employer': [sum_amount_qp_employer]
        })

        df = pd.concat([df, total_df], ignore_index=True)

        for column in ['amount_qp_employee', 'amount_qp_employer']:
            df[column] = df[column].apply(intcomma)

        columns = {
            'employee__registration_number': 'matricule',
            'employee__last_name': 'nom',
            'employee__middle_name': 'post nom',
            'amount_qp_employee': 'montant qqe',
            'amount_qp_employer': 'montant qqp'
        }
        df.columns = [columns.get(col, col) for col in df.columns]

        df = df.to_html(index=False, classes='table table-striped mt-3')
        df = df.replace('<th>', '<th style="text-align: left;" class="text-capitalize">')

        return render(request, "payroll/listing.html", locals())
