# payroll/views/listing.py or wherever appropriate

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib import messages
from django.apps import apps
import pandas as pd
from core.views import BaseView
from django.db.models import F
import logging

logger = logging.getLogger(__name__)


def intcomma(value):
    """
    Format a numeric value with commas safely.

    Args:
        value (float|int): The number to format.

    Returns:
        str: Formatted string or '0' if invalid.
    """
    if pd.isna(value) or value is None:
        return "0"
    try:
        # Ensure value is numeric before formatting
        numeric_value = float(abs(value))
        return "{:,}".format(round(numeric_value, 2))
    except (ValueError, TypeError):
        return str(value)


class Listing(BaseView):
    """
    A performance-optimized view for generating a payroll listing as an HTML table.

    Features:
      - Retrieves payroll item data based on code and payroll ID
      - Aggregates employee contributions
      - Formats numbers safely
      - Renders HTML table dynamically using Pandas
    """

    def get(self, request, pk):
        """
        Handles GET requests to generate and display the listing report.
        """
        logger.info(f"User {request.user} requested payroll listing for Payroll ID={pk}")

        try:
            Payroll = apps.get_model("payroll", "Payroll")
            ItemPaid = apps.get_model("payroll", "ItemPaid")

            # Retrieve the payroll object or raise 404
            payroll_obj = get_object_or_404(Payroll, id=pk)
            logger.debug(f"Found Payroll: {payroll_obj}")

            # Get 'code' from query parameters
            code = request.GET.get("code")
            if not code:
                logger.warning("No 'code' provided in request.")
                messages.warning(request, "Code de l'élément non fourni.")
                return redirect(reverse_lazy("payroll:payslips", kwargs={"pk": payroll_obj.pk}))

            # Try to find matching item
            from payroll.models import Item, LegalItem
            item = Item.objects.filter(code=code).first() or LegalItem.objects.filter(code=code).first()

            if not item:
                logger.warning(f"No item found with code={code}")
                messages.warning(request, "Élément introuvable.")
                return redirect(reverse_lazy("payroll:payslips", kwargs={"pk": payroll_obj.pk}))

            logger.debug(f"Found item: {item.code} - {item.name}")

            # Fetch related ItemPaid records
            itempaid_qs = ItemPaid.objects.filter(
                code=code,
                employee__payroll=payroll_obj
            ).annotate(
                registration_number=F('employee__registration_number'),
                last_name=F('employee__last_name'),
                middle_name=F('employee__middle_name')
            ).values_list(
                'registration_number',
                'last_name',
                'middle_name',
                'amount_qp_employee',
                'amount_qp_employer'
            )

            if not itempaid_qs.exists():
                logger.info(f"No data found for item '{code}' under Payroll ID={pk}")
                messages.info(request, "Aucune donnée trouvée pour cet élément.")
                return redirect(reverse_lazy("payroll:payslips", kwargs={"pk": payroll_obj.pk}))

            # Convert directly to DataFrame
            columns = ['registration_number', 'last_name', 'middle_name', 'amount_qp_employee', 'amount_qp_employer']
            df = pd.DataFrame(list(itempaid_qs), columns=columns)

            # Add total row
            total_row = {
                "registration_number": "Total",
                "last_name": "",
                "middle_name": "",
                "amount_qp_employee": intcomma(df["amount_qp_employee"].sum()),
                "amount_qp_employer": intcomma(df["amount_qp_employer"].sum())
            }

            df = pd.concat([df, pd.DataFrame([total_row])], ignore_index=True)

            # Rename columns for better readability in template
            column_mapping = {
                "registration_number": "Matricule",
                "last_name": "Nom",
                "middle_name": "Postnom",
                "amount_qp_employee": "Montant QQP Employé",
                "amount_qp_employer": "Montant QQP Employeur",
            }
            df.rename(columns=column_mapping, inplace=True)

            # Generate styled HTML table
            html_table = df.to_html(index=False, classes="table table-striped mt-3")
            html_table = html_table.replace('<th>', '<th style="text-align: left;" class="text-capitalize">')

            logger.info(f"Generated listing for item '{code}' with {len(df)} rows.")
            return render(request, "payroll/listing.html", locals())

        except Exception as e:
            logger.error(f"Error generating listing for Payroll ID={pk}, code='{code}': {e}", exc_info=True)
            messages.error(request, f"Erreur lors de la génération du listing: {str(e)}")
            return redirect(reverse_lazy("payroll:payslips", kwargs={"pk": pk}))