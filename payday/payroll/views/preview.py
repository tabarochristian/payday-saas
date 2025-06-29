# payroll/views/preview.py

from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.translation import gettext_lazy as _
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Model
from django.conf import settings
from django.apps import apps


from core.forms.button import Button
from core.views import Change
import logging

logger = logging.getLogger(__name__)


class Preview(Change):
    """
    A view to preview payroll operations before finalizing the payslip process.
    
    Features:
      - Redirects if payroll already processed
      - Estimates duration based on employee/item count
      - Dynamically generates action buttons
      - Triggers async payroll processing
    """
    template_name = "payroll/preview.html"
    PAYROLL_STATUSES = ("IN_PROGRESS", "COMPLETED", "ERROR", "APPROVED", "REJECTED")
    
    @property
    def model_class(self):
        """Return the model class from URL kwargs."""
        return apps.get_model("payroll", model_name="payroll")

    def get_action_buttons(self):
        """
        Returns custom action buttons for the preview page.
        Removes default Save/Delete buttons and adds 'Start Payroll' button.
        """
        logger.debug("Generating action buttons for preview view.")
        kwargs = self.kwargs

        # Get parent buttons and remove last two (Save/Delete)
        buttons = super().get_action_buttons()
        buttons = buttons[:-1]  # Remove last two buttons safely

        start_button = Button(
            tag="button",
            classes="btn btn-success",
            text=_("Commencer la paie"),
            permission=f"{kwargs['app']}.change_{kwargs['model']}",
            attrs={
                "type": "submit",
                "form": f"form-{kwargs['model']}",
                "value": "IN_PROGRESS",
                "name": "status"
            },
        )
        buttons.append(start_button)

        return [btn for btn in buttons if btn.permission and self.request.user.has_perm(btn.permission)]

    def estimate_duration(self, queryset, payroll_obj) -> timedelta:
        """
        Estimate time required to process this payroll based on number of employees and items.

        Args:
            queryset (QuerySet): PaidEmployee queryset
            payroll_obj (Payroll): Payroll instance

        Returns:
            timedelta: Estimated duration
        """
        try:
            item_model = apps.get_model("payroll", "item")
            legal_item_model = apps.get_model("payroll", "legalitem")
            total_items = item_model.objects.count() + legal_item_model.objects.count()
            duration = timedelta(milliseconds=total_items * queryset.count() * 3)
            logger.info(f"Estimated processing duration: {duration}")
            return duration
        except Exception as e:
            logger.warning(f"Failed to estimate duration: {e}")
            return timedelta(seconds=0)

    def get(self, request, pk):
        """
        Handles GET requests to show payroll preview.

        If the payroll has already been processed, redirects to payslips view.
        Otherwise, prepares context and renders the preview template.
        """
        logger.info(f"User {request.user} requested payroll preview for ID={pk}")

        try:
            self.kwargs.update({"app": "payroll", "model": "payroll"})
            model_class = self.model_class
            payroll_obj = get_object_or_404(model_class, pk=pk)

            paid_employee_model = apps.get_model("payroll", "paidemployee")
            paid_employees_qs = paid_employee_model.objects.filter(payroll=payroll_obj)

            if payroll_obj.status in self.PAYROLL_STATUSES:
                logger.info(f"Payroll ID={pk} already processed. Redirecting to payslips.")
                return redirect("payroll:payslips", pk=pk)

            estimation_duration = self.estimate_duration(paid_employees_qs, payroll_obj)
            action_buttons = self.get_action_buttons()

            logger.debug("Rendering payroll preview template.")
            return render(request, self.template_name, locals())

        except Exception as e:
            logger.error(f"GET request failed for Payroll ID={pk}: {str(e)}", exc_info=True)
            messages.error(request, _("Échec du chargement de l'aperçu de la paie"))
            return redirect(reverse_lazy("core:home"))

    def post(self, request, pk):
        """
        Handle POST to update payroll status and trigger background processing.

        Changes payroll status to IN_PROGRESS and triggers async payroll generation.
        """
        logger.info(f"User {request.user} triggered payroll processing for ID={pk}")

        try:
            self.kwargs.update({"app": "payroll", "model": "payroll"})
            model_class = self.model_class
            payroll_obj = get_object_or_404(model_class, pk=pk)

            data = request.POST.dict()
            new_status = data.get("status")

            if new_status and new_status in self.PAYROLL_STATUSES:
                payroll_obj.status = new_status
                payroll_obj.save(update_fields=["status"])
                messages.success(request, _("La paie a commencé."))

            # Trigger async payroll processing
            from payroll.tasks import Payer
            host = request.get_host().split(".")[0]
            logger.info(f"Triggering async payroll processor for schema: {host}, payroll_id={pk}")
            payer = Payer()

            # Fetch the debug setting with a default of False for better safety
            debug_mode = getattr(settings, "DEBUG", False)

            # Use a ternary operator for cleaner execution logic
            action = payer.run if debug_mode else payer.delay
            action(host, pk)

            return redirect("payroll:payslips", pk=pk)

        except Exception as e:
            logger.exception(f"POST request failed for Payroll ID={pk}: {str(e)}")
            messages.error(request, _("Une erreur est survenue lors du démarrage de la paie."))
            return redirect(reverse_lazy("core:home"))