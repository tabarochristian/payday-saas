# payroll/views/canvas.py or wherever appropriate

from employee.models import Employee
from django.http import HttpResponse
from core.views import BaseViewMixin
import pandas as pd

from django.db.models import F, Value as V, CharField
from django.db.models.functions import Concat

from django.shortcuts import redirect
from django.utils.text import slugify
from django.contrib import messages
from django.http import Http404
from django.db import models

# Import logging
import logging
logger = logging.getLogger(__name__)


class Canvas(BaseViewMixin):
    """
    A high-performance view for generating Excel exports of employee data.

    Supports:
        - tracker(): Exports grouped employee tracker data (grouped by branch).
        - benefits(): Exports predefined benefit templates.
    """

    headers = [{
        'matricule': None,
        "type d'element": 1,
        'code': None,
        'nom': None,
        'montant quote part employee': 0,
        'montant quote part employeur': 0,
        'plafond de la sécurité sociale': 0,
        'montant imposable': 0,
        'est une prime': 0,
        'est payable': 1,
    }]

    def get(self, request, actor):
        """
        Dispatch to export method dynamically based on `actor`.
        """
        logger.info(f"User {request.user} is attempting to access export method: {actor}")
        export_method = getattr(self, actor, None)

        if not export_method or not callable(export_method):
            logger.warning(f"Export method '{actor}' not found in Canvas view.")
            raise Http404("Export method not found")

        try:
            result = export_method()
            logger.info(f"Successfully executed export method: {actor}")
            return result
        except Exception as e:
            logger.error(f"Error occurred in export method '{actor}': {str(e)}", exc_info=True)
            messages.error(request, f"Erreur lors de l'exécution de l'export '{actor}': {str(e)}")
            return redirect(self.request.META.get('HTTP_REFERER'))

    def tracker(self):
        """
        Generate Excel file grouped by branch from filtered employee data.
        """
        logger.info("Starting export: tracker")

        query_params = {
            key: value.split(',') if '__in' in key else value
            for key, value in self.request.GET.items() if value
        }

        logger.debug(f"Applying filters: {query_params}")

        # Efficient field selection using only needed fields
        try:
            qs = Employee.objects.filter(**query_params).annotate(
                full_name=Concat(
                    F('last_name'), V(' '), F('middle_name'),
                    output_field=CharField()
                ),
                branch_name=F('branch__name'),
                grade_name=F('grade__name')
            ).values(
                'registration_number',
                'full_name',
                'branch_name',
                'grade_name'
            )
        except Exception as e:
            logger.error(f"Query error in tracker export: {e}", exc_info=True)
            messages.error(self.request, "Erreur dans les paramètres de filtre.")
            return redirect(self.request.META.get('HTTP_REFERER'))

        if not qs.exists():
            logger.warning("No employees matched the filters in tracker export")
            messages.warning(self.request, "Aucun employé trouvé avec les filtres appliqués.")
            return redirect(self.request.META.get('HTTP_REFERER'))

        # Convert directly to DataFrame without intermediate list/dict step
        df = pd.DataFrame(qs)
        df.rename(columns={
            'branch_name': 'branch',
            'grade_name': 'grade'
        }, inplace=True)

        additional_columns = ['absence', 'absence.justifiee']
        for col in additional_columns:
            df[col] = 0  # Set default values

        logger.debug(f"Loaded {len(df)} records for export.")

        # Sort once before grouping
        df.sort_values(by=['grade', 'registration_number', 'full_name'], ascending=[True, True, True], inplace=True)

        group_by = 'branch'

        # Initialize response
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="canvas.xlsx"'

        try:
            with pd.ExcelWriter(response, engine='xlsxwriter') as writer:
                if group_by in df.columns:
                    logger.info(f"Grouping data by '{group_by}' and writing sheets...")
                    # Group by specified column and write each group to separate sheet
                    for group_value, group_df in df.groupby(group_by):
                        sheet_name = slugify(str(group_value))[:31]  # Sheet names are limited to 31 chars
                        logger.debug(f"Writing sheet: {sheet_name} with {len(group_df)} rows")
                        group_df.to_excel(writer, sheet_name=sheet_name, index=False)
                else:
                    logger.debug("No valid group column. Exporting all data to single sheet.")
                    df.to_excel(writer, sheet_name='global', index=False)

            logger.info("Tracker export completed successfully.")
            return response
        except Exception as e:
            logger.error(f"Error during Excel generation: {str(e)}", exc_info=True)
            messages.error(self.request, "Erreur lors de la génération du fichier Excel.")
            return redirect(self.request.META.get('HTTP_REFERER'))

    def benefits(self):
        """
        Generate an Excel template for benefit items.
        """
        logger.info("Starting export: benefits")

        try:
            df = pd.DataFrame(self.headers)
            logger.debug(f"Generated benefits template with {len(df.columns)} columns")
        except Exception as e:
            logger.error(f"Failed to load benefit headers: {str(e)}", exc_info=True)
            messages.error(self.request, "Échec de chargement des en-têtes.")
            return redirect(self.request.META.get('HTTP_REFERER'))

        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="canvas-items-to-pay.xlsx"'

        try:
            with pd.ExcelWriter(response, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='global', index=False)
            logger.info("Benefits export completed successfully.")
            return response
        except Exception as e:
            logger.error(f"Error during benefits export: {str(e)}", exc_info=True)
            messages.error(self.request, "Échec de la génération du fichier Excel.")
            return redirect(self.request.META.get('HTTP_REFERER'))