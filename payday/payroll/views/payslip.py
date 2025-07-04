# payroll/views/payslip.py

from django.shortcuts import render, redirect, get_object_or_404
from django.utils.translation import gettext as _
from django.urls import reverse_lazy
from django.db import transaction
from django.forms import CheckboxInput
from django.contrib import messages
from django.apps import apps
import logging

from core.forms import modelform_factory
from core.forms.button import Button
from core.views import Change
from payroll import models

logger = logging.getLogger(__name__)


class Payslip(Change):
    """
    A view for viewing and editing payslips for PaidEmployee objects.
    """

    template_name = "payroll/payslip.html"

    @property
    def model_class(self):
        return apps.get_model("payroll", "PaidEmployee")

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm("payroll.change_paidemployee"):
            messages.warning(request, _("Vous n'avez pas la permission de modifier cet objet."))
            return redirect(reverse_lazy("payroll:slips", kwargs={
                "pk": self.kwargs["pk"]
            }))
        self.next = request.GET.get("next")
        return super().dispatch(request, *args, **kwargs)

    def get_action_buttons(self, obj=None):
        obj = obj or self._get_object()
        parent_buttons = [
            btn for btn in super().get_action_buttons(obj)
            if not any(label in btn.text for label in [_("Sauvegarder"), _("Supprimer")])
        ]

        print_button = Button(
            tag='a',
            text=_("Bulletin de paie"),
            url=reverse_lazy("payroll:slips") + f"?pk={obj.pk}",
            classes="btn btn-light-primary",
            permission="payroll.view_paidemployee",
        )

        extra_buttons = []
        get_extra_buttons = getattr(obj, "get_action_buttons", None)

        try:
            if callable(get_extra_buttons):
                result = get_extra_buttons()
                extra_buttons = [Button(**b) for b in (result if isinstance(result, (list, tuple)) else [result])]
            elif isinstance(get_extra_buttons, (list, tuple)):
                extra_buttons = [Button(**b) for b in get_extra_buttons]
            elif isinstance(get_extra_buttons, dict):
                extra_buttons = [Button(**get_extra_buttons)]
        except Exception as e:
            logger.warning(f"Failed to load extra buttons: {e}", exc_info=True)

        all_buttons = extra_buttons + parent_buttons + [print_button]
        return [btn for btn in all_buttons if not btn.permission or self.request.user.has_perm(btn.permission)]

    def get_display_fields(self):
        try:
            return [
                field for field in self.model_class._meta.fields
                if hasattr(self.model_class, 'list_display') and field.name in self.model_class.list_display
            ]
        except Exception as e:
            logger.error(f"Error retrieving display fields: {e}", exc_info=True)
            return []

    def configure_form_fields(self, form):
        for field in ['social_security_amount', 'taxable_amount']:
            if field in form.fields:
                form.fields[field].widget = CheckboxInput()
                form.fields[field].required = False
        return form

    def get(self, request, pk):
        self.kwargs.update({
            'app': 'payroll',
            'model': 'paidemployee'
        })

        try:
            model_class = self.model_class
            employee_obj = get_object_or_404(model_class, pk=pk)
            items = employee_obj.itempaid_set.select_related('employee').order_by('code')
            form_class = modelform_factory(models.ItemPaid)
            form = self.configure_form_fields(form_class())

            action_buttons = self.get_action_buttons(employee_obj)
            display_fields = self.get_display_fields()
            return render(request, self.template_name, locals())
        except Exception as e:
            logger.error(f"Failed to load payslip view for ID={pk}: {e}", exc_info=True)
            messages.error(request, _("Erreur lors du chargement de la fiche de paie."))
            return redirect(self.next or reverse_lazy("core:home"))

    @transaction.atomic
    def post(self, request, pk):
        try:
            model_class = self.model_class
            employee_obj = get_object_or_404(model_class, pk=pk)
            form_class = modelform_factory(models.ItemPaid)
            form = self.configure_form_fields(form_class(request.POST))

            if not form.is_valid():
                messages.error(request, _("Veuillez corriger les erreurs dans le formulaire."))
                items = employee_obj.itempaid_set.select_related("employee").order_by("code")
                action_buttons = self.get_action_buttons(employee_obj)
                display_fields = self.get_display_fields()
                return render(request, self.template_name, locals())

            instance = form.save(commit=False)
            instance.employee = employee_obj
            instance.is_payable = True
            instance.is_bonus = False

            if not hasattr(instance, "type_of_item") or instance.type_of_item is None:
                messages.error(request, _("Type d'élément manquant ou invalide."))
                return render(request, self.template_name, locals())

            type_multiplier = instance.type_of_item

            instance.amount_qp_employee = abs(instance.amount_qp_employee) * type_multiplier
            instance.amount_qp_employer = abs(instance.amount_qp_employer)
            instance.sub_organization = employee_obj.sub_organization

            instance.social_security_amount = (
                abs(instance.amount_qp_employee) * type_multiplier
                if form.cleaned_data.get("social_security_amount")
                else 0
            )
            instance.taxable_amount = (
                abs(instance.amount_qp_employee) * type_multiplier
                if form.cleaned_data.get("taxable_amount")
                else 0
            )

            instance.save()

            # Update parent records
            employee_obj.update()
            employee_obj.payroll.update()

            messages.success(request, _("L'élément a été ajouté avec succès."))
            return redirect(request.META.get("HTTP_REFERER", self.next or reverse_lazy("core:list", kwargs={
                "app": "payroll",
                "model": "paidemployee"
            })))

        except Exception as e:
            logger.error(f"POST failed for Payslip ID={pk}: {e}", exc_info=True)
            messages.error(request, _("Une erreur est survenue lors de l'ajout de l'élément."))
            return redirect(request.get_full_path())