from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib import messages
from django.apps import apps
import pandas as pd
import json
from core.views import BaseView

# Define a helper function to format numbers with commas.
def intcomma(value):
    """
    Format a numeric value with commas.
    
    Args:
        value (numeric): The number to format.
        
    Returns:
        str: The formatted string.
    """
    return "{:,}".format(round(abs(value), 2))


class Listing(BaseView):
    """
    A view for generating a payroll listing exported as an HTML table.

    This view retrieves payroll item data based on a given 'code' (passed as a GET
    parameter) and the specified payroll (identified by primary key). It then processes 
    the data using pandas to calculate totals, apply numeric formatting, rename columns, 
    and finally convert the result into an HTML table.
    """
    def get(self, request, pk):
        # Retrieve the Payroll and ItemPaid models.
        Payroll = apps.get_model('payroll', 'payroll')
        ItemPaid = apps.get_model('payroll', 'itempaid')

        # Extract query parameters from the GET request.
        query_params = request.GET.dict()

        # Retrieve the Payroll object; raise 404 if not found.
        payroll_obj = get_object_or_404(Payroll, id=pk)
        
        # Extract the 'code' parameter, then remove it from the query dict.
        code = query_params.pop('code', None)
        if not code:
            messages.warning(request, 'Item not found.')
            return redirect(reverse_lazy('payroll:payslips', kwargs={'pk': payroll_obj.pk}))

        # Retrieve the item by its code from either Item or LegalItem (fallback).
        # Importing these models here to avoid circular imports.
        from payroll.models import Item, LegalItem
        item = Item.objects.filter(code=code).first() or LegalItem.objects.filter(code=code).first()

        # Retrieve ItemPaid records related to this payroll that match the given code.
        itempaid_qs = ItemPaid.objects.filter(code=code, employee__payroll=payroll_obj).values(
            'employee__registration_number',
            'employee__last_name',
            'employee__middle_name',
            'amount_qp_employee',
            'amount_qp_employer'
        )
        
        # Convert the queryset to a pandas DataFrame.
        df = pd.DataFrame(list(itempaid_qs))

        # Calculate the total amounts for employee and employer contributions.
        sum_amount_qp_employee = df['amount_qp_employee'].sum() if not df.empty else 0
        sum_amount_qp_employer = df['amount_qp_employer'].sum() if not df.empty else 0

        # Create a DataFrame representing a row with the totals.
        total_df = pd.DataFrame({
            'employee__registration_number': ['Total'],
            'employee__last_name': [''],
            'employee__middle_name': [''],
            'amount_qp_employee': [sum_amount_qp_employee],
            'amount_qp_employer': [sum_amount_qp_employer]
        })

        # Append the totals row to the data.
        df = pd.concat([df, total_df], ignore_index=True)

        # Apply numeric formatting to the specified columns.
        for column in ['amount_qp_employee', 'amount_qp_employer']:
            df[column] = df[column].apply(intcomma)

        # Map original column names to desired header names.
        column_mapping = {
            'employee__registration_number': 'matricule',
            'employee__last_name': 'nom',
            'employee__middle_name': 'post nom',
            'amount_qp_employee': 'montant qqe',
            'amount_qp_employer': 'montant qqp'
        }
        df.columns = [column_mapping.get(col, col) for col in df.columns]

        # Convert the DataFrame to an HTML table with appropriate styling.
        html_table = df.to_html(index=False, classes='table table-striped mt-3')
        html_table = html_table.replace(
            '<th>', '<th style="text-align: left;" class="text-capitalize">'
        )
        return render(request, "payroll/listing.html", locals())
