# payroll/views/synthesis.py

from django.utils.translation import gettext_lazy as _
from django.shortcuts import render, redirect, get_object_or_404
from django.apps import apps
from django.db.models import Model
import pandas as pd
from core.views import BaseViewMixin
from django.contrib import messages
from django.urls import reverse_lazy
import logging

logger = logging.getLogger(__name__)


def intcomma(value):
    """
    Format numeric value with commas.
    """
    if isinstance(value, (int, float)):
        return f"{value:,.2f}"
    return str(value) if value is not None else ""


def get_name_of_fields(field_list):
    """
    Extract field names from Django model fields.
    """
    return [field.name for field in field_list]


class Synthesis(BaseViewMixin):
    """
    A class-based view that generates synthesis reports using pivot tables.

    Features:
      - User selects row/column fields via POST
      - Aggregation function can be 'sum', 'mean', etc.
      - Uses Pandas for dynamic data transformation
      - Renders result in HTML table
    """
    action = ["view"]
    template_name = "payroll/synthesis.html"
    template_name_field_selector = "payroll/field_selector.html"

    def get_field_verbose(self, model, field: str):
        """
        Recursively retrieve verbose name for nested field (e.g., employee__branch__name).
        """
        parts = field.split("__")
        current_model = model
        current_field = None

        try:
            for part in parts:
                current_field = current_model._meta.get_field(part)
                if current_field.is_relation:
                    current_model = current_field.related_model
            return current_field.verbose_name.lower()
        except Exception as e:
            logger.warning(f"Field '{field}' does not exist on {model.__name__}: {str(e)}")
            return field  # fallback

    def get_field(self, model, field):
        """
        Recursively retrieves the field object for nested fields.
        """
        parts = field.split("__")
        current_model = model

        try:
            for part in parts[:-1]:
                current_model = current_model._meta.get_field(part).related_model
            return current_model._meta.get_field(parts[-1])
        except Exception as e:
            logger.warning(f"Failed to get field '{field}': {str(e)}")
            raise Http404(_("Champ introuvable"))

    def get(self, request, func, pk):
        """
        Render the field selector template where user chooses pivot dimensions.
        """
        logger.info(f"User {request.user} requested synthesis field selection for Payroll ID={pk}")

        try:
            self.kwargs.update({"app": "payroll", "model": "paidemployee"})
            model_class = apps.get_model("payroll", "paidemployee")
            payroll_obj = get_object_or_404(model_class.payroll.field.remote_field.model, id=pk)

            return render(request, self.template_name_field_selector, {
                "pk": pk,
                "func": func,
                "payroll_obj": payroll_obj,
                "model_class": model_class,
                "model_class_meta": model_class._meta,
                "title": _("Sélectionnez les champs pour la synthèse"),
            })

        except Exception as e:
            logger.error(f"GET request failed for Synthesis view: {str(e)}", exc_info=True)
            messages.error(request, _("Échec du chargement de la sélection de champ."))
            return redirect(reverse_lazy("core:home"))

    def post(self, request, func, pk):
        """
        Handle POST requests to generate a synthesis report (pivot table) based on selected fields.
        """
        logger.info(f"User {request.user} submitted synthesis form for Payroll ID={pk}, func={func}")
        
        try:
            # Load models
            payroll_model = apps.get_model("payroll", "payroll")
            paidemployee_model = apps.get_model("payroll", "paidemployee")

            # Get payroll object
            payroll_obj = get_object_or_404(payroll_model, id=pk)

            # Query related paid employees
            qs = paidemployee_model.objects.filter(payroll=payroll_obj)
            if not qs.exists():
                messages.warning(request, _("Aucune donnée trouvée pour ce rapport"))
                return redirect(request.META.get("HTTP_REFERER", reverse_lazy("core:home")))

            # Process selected fields
            post_dict = request.POST.dict()
            selected_fields = [v for k, v in post_dict.items() if k != "csrfmiddlewaretoken"]

            if not selected_fields:
                messages.warning(request, _("Veuillez sélectionner au moins un champ."))
                return redirect(request.META.get("HTTP_REFERER", reverse_lazy("core:home")))

            if "net" not in selected_fields:
                selected_fields.append("net")

            # Retrieve values
            data = list(qs.values(*selected_fields))

            if not data:
                messages.warning(request, _("Aucune donnée disponible pour ces filtres."))
                return redirect(request.META.get("HTTP_REFERER", reverse_lazy("core:home")))

            df = pd.DataFrame(data)
            pivot_index = request.POST.get("column")
            pivot_columns = request.POST.get("row")

            if not pivot_index or not pivot_columns:
                messages.warning(request, _("Vous devez spécifier un champ en colonne et un champ en ligne."))
                return redirect(request.META.get("HTTP_REFERER", reverse_lazy("core:home")))

            # Build pivot table
            try:
                df_pivot = df.pivot_table(
                    index=pivot_index,
                    columns=pivot_columns,
                    values="net",
                    aggfunc=func,
                    fill_value=0
                )
            except Exception as e:
                logger.error(f"Pivot table generation failed: {str(e)}")
                messages.error(request, _("Échec de la génération du tableau croisé dynamique."))
                return redirect(request.META.get("HTTP_REFERER", reverse_lazy("core:home")))

            # Add totals
            df_pivot["Total"] = df_pivot.sum(axis=1)
            total_row = df_pivot.sum(axis=0)
            total_row.name = "Total"
            df_pivot = pd.concat([df_pivot, pd.DataFrame([total_row])])

            # Rename column names to verbose labels
            field_verbose_map = {
                field: self.get_field_verbose(paidemployee_model, field) for field in selected_fields
            }
            df_pivot.reset_index(inplace=True)
            df_pivot.rename(columns=field_verbose_map, inplace=True)
            df_pivot.columns.name = None

            # Format numbers if sum
            if func == "sum":
                df_pivot = df_pivot.applymap(intcomma)

            # Prepare final context
            row_verbose = self.get_field_verbose(paidemployee_model, pivot_columns)
            col_verbose = self.get_field_verbose(paidemployee_model, pivot_index)

            return render(request, self.template_name, {
                "html_table": df_pivot.to_html(index=False, classes="table table-striped mt-3").replace(
                    'text-align: right;', 'text-align: left;'
                ),
                "title": _("Synthèse par ") + func,
                "payroll_obj": payroll_obj,
                "row_label": row_verbose.title(),
                "col_label": col_verbose.title(),
                "func": func,
            })

        except Exception as e:
            logger.exception(f"POST request failed for Synthesis ID={pk}: {str(e)}")
            messages.error(request, _("Une erreur est survenue lors de la génération de la synthèse."))
            return redirect(reverse_lazy("core:home"))