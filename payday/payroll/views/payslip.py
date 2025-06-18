# payroll/views/payslip.py

from django.shortcuts import render, redirect, get_object_or_404
from django.utils.translation import gettext as _
from django.urls import reverse_lazy
from django.db import transaction
from django.forms import CheckboxInput
from core.forms import modelform_factory
from core.forms.button import Button
from core.views import Change
from payroll import models
from django.contrib import messages
from core.models import Base
from django.apps import apps
import logging

logger = logging.getLogger(__name__)


class Payslip(Change):
    """
    A view for viewing and editing payslips.
    Uses locals() for fast template rendering.
    """
    template_name = "payroll/payslip.html"

    def get_model(self):
        return apps.get_model('payroll', model_name='paidemployee')

    def dispatch(self, request, *args, **kwargs):
        model_class = self.get_model()
        change_perm = f"{model_class._meta.app_label}.change_{model_class._meta.model_name}"
        
        if not request.user.has_perm(change_perm):
            messages.warning(request, _("Vous n'avez pas la permission de modifier cet objet."))
            return redirect(reverse_lazy("core:home"))

        self.next = request.GET.get('next')
        return super().dispatch(request, *args, **kwargs)

    def get_action_buttons(self, obj=None):
        obj = obj or self._get_object()
        app = 'payroll'
        model = 'paidemployee'
        parent_buttons = [
            btn for btn in super().get_action_buttons(obj)
            if not any(text in btn.text for text in ["Sauvegarder", "Supprimer"])
        ]
        print_button = Button(
            tag='a',
            text=_('Bulletin de paie'),
            url=reverse_lazy('payroll:slips') + f"?pk={obj.pk}",
            classes='btn btn-light-primary',
            permission=f"{app}.{model}.view"
        )
        extra_buttons = []
        get_extra_buttons = getattr(obj, 'get_action_buttons', None)

        if callable(get_extra_buttons):
            result = get_extra_buttons()
            if isinstance(result, (list, tuple)):
                extra_buttons = [Button(**b) for b in result]
            elif result:
                extra_buttons = [Button(**result)]
        elif get_extra_buttons is not None:
            if isinstance(get_extra_buttons, (list, tuple)):
                extra_buttons = [Button(**b) for b in get_extra_buttons]
            else:
                extra_buttons = [Button(**get_extra_buttons)]

        all_buttons = extra_buttons + parent_buttons + [print_button]
        return [btn for btn in all_buttons if self.request.user.has_perm(btn.permission)]

    def get_display_fields(self):
        try:
            model_class = apps.get_model('payroll', 'paidemployee')
            return [field for field in model_class._meta.fields if field.name in model_class.list_display]
        except Exception as e:
            logger.error(f"Error retrieving display fields for PaidEmployee: {str(e)}")
            return []

    def configure_form_fields(self, form):
        for field in ['social_security_amount', 'taxable_amount']:
            form.fields[field].widget = CheckboxInput()
            form.fields[field].required = False
        return form

    def get(self, request, pk):
        try:
            self.kwargs.update({'app': 'payroll', 'model': 'paidemployee'})
            model_class = apps.get_model('payroll', 'paidemployee')
            employee_obj = get_object_or_404(model_class, pk=pk)
            items = employee_obj.itempaid_set.all()\
                .select_related('employee').order_by('code')
            ItemPaidForm = modelform_factory(models.ItemPaid)
            form = self.configure_form_fields(ItemPaidForm())
            action_buttons = self.get_action_buttons(employee_obj)
            display_fields = self.get_display_fields()

            # ✅ Using locals() here for quick template rendering
            return render(request, self.template_name, locals())

        except Exception as e:
            logger.error(f"GET request failed for Payslip ID={pk}: {str(e)}", exc_info=True)
            messages.error(request, _("Une erreur est survenue lors du chargement de la fiche de paie."))
            return redirect(self.next or reverse_lazy("core:home"))

    @transaction.atomic
    def post(self, request, pk):
        try:
            self.kwargs.update({"app": "payroll", "model": "paidemployee"})
            model_class = apps.get_model("payroll", "paidemployee")
            employee_obj = get_object_or_404(model_class, pk=pk)
            ItemPaidForm = modelform_factory(models.ItemPaid)
            form = self.configure_form_fields(ItemPaidForm(request.POST))

            if not form.is_valid():
                messages.error(request, _("Remplissez correctement le formulaire"))
                items = employee_obj.itempaid_set.select_related("employee").order_by("code")
                action_buttons = self.get_action_buttons(employee_obj)
                display_fields = self.get_display_fields()
                return render(request, self.template_name, locals())

            instance = form.save(commit=False)

            if not hasattr(instance, "type_of_item") or instance.type_of_item is None:
                logger.error(f"ItemPaid missing type_of_item for Payslip ID={pk}")
                messages.error(request, _("Type d'élément invalide."))
                return render(request, self.template_name, locals())

            instance.employee = employee_obj
            instance.is_payable = True
            instance.is_bonus = False

            instance.amount_qp_employee = abs(instance.amount_qp_employee) * instance.type_of_item
            instance.amount_qp_employer = abs(instance.amount_qp_employer)

            instance.social_security_amount = (
                abs(instance.amount_qp_employee) * instance.type_of_item
                if form.cleaned_data.get("social_security_amount")
                else 0
            )
            instance.taxable_amount = (
                abs(instance.amount_qp_employee) * instance.type_of_item
                if form.cleaned_data.get("taxable_amount")
                else 0
            )

            instance.save()

            employee_obj.update()
            employee_obj.payroll.update()

            messages.success(request, _("L'élément a été ajouté avec succès"))
            next_url = request.META.get("HTTP_REFERER", self.next or reverse_lazy("core:list", kwargs={
                "app": "payroll",
                "model": "paidemployee"
            }))
            return redirect(next_url)

        except Exception as e:
            logger.error(f"POST request failed for Payslip ID={pk}: {str(e)}", exc_info=True)
            messages.error(request, _("Une erreur est survenue lors de l'ajout de l'élément."))
            items = employee_obj.itempaid_set.select_related("employee").order_by("code")
            action_buttons = self.get_action_buttons(employee_obj)
            display_fields = self.get_display_fields()
            return render(request, self.template_name, locals())