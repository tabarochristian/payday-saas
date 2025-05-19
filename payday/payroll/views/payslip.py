from django.shortcuts import render, redirect, get_object_or_404
from django.utils.translation import gettext as _
from django.contrib import messages
from django.urls import reverse_lazy
from django.apps import apps
from django.db import transaction
from django.forms import CheckboxInput
from core.forms import modelform_factory
from core.forms.button import Button
from core.views import Change
from payroll import models
from core.models import Base
import logging

logger = logging.getLogger(__name__)

class Payslip(Change):
    """
    A view for updating payroll data related to a specific paid employee, with functionality
    to view and print the corresponding payslip.

    Extends the base Change view, customizing action buttons, GET, and POST handling for
    paid employee payroll items.
    """
    template_name = "payroll/payslip.html"

    def get_model(self):
        """
        Returns the PaidEmployee model.

        Returns:
            Model: The PaidEmployee model from the payroll app.
        """
        return apps.get_model('payroll', model_name='paidemployee')

    def dispatch(self, request, *args, **kwargs):
        """
        Validates user permissions before processing the request.

        Args:
            request (HttpRequest): The incoming request.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            HttpResponse: Redirects to home if permission is lacking, else proceeds.
        """
        model_class = self.get_model()
        change_perm = f"{model_class._meta.app_label}.change_{model_class._meta.model_name}"

        if not request.user.has_perm(change_perm):
            messages.warning(request, _("Vous n'avez pas la permission de modifier cet objet."))
            return redirect(reverse_lazy("core:home"))

        self.next = request.GET.get('next')
        return super().dispatch(request, *args, **kwargs)

    def get_action_buttons(self, obj=None):
        """
        Generates action buttons for the payslip view, including a Print button.

        Args:
            obj: Optional model instance (PaidEmployee) for context-specific buttons.

        Returns:
            list: A list of Button objects filtered by user permissions.
        """
        obj = obj or self._get_object()
        app = 'payroll'
        model = 'paidemployee'
        model_permission_prefix = f"{app}.{model}"

        # Filter parent buttons to exclude irrelevant ones (e.g., Save, Delete)
        parent_buttons = [
            btn for btn in super().get_action_buttons(obj)
            if 'Sauvegarder' not in btn.text and 'Supprimer' not in btn.text
        ]

        buttons = [
            Button(
                tag='a',
                text=_('Bulletin de paie'),
                url=reverse_lazy('payroll:slips') + f"?pk={obj.pk}",
                classes='btn btn-light-primary',
                permission=f"{model_permission_prefix}.view"
            )
        ]

        # Handle model-specific extra buttons
        get_action_buttons = getattr(obj, 'get_action_buttons', None)
        extra_buttons = []
        
        if callable(get_action_buttons):
            result = get_action_buttons()
            if isinstance(result, (list, tuple)):
                extra_buttons = [Button(**button) for button in result]
            elif result is not None:
                extra_buttons = [Button(**result)]
        elif get_action_buttons is not None:
            if isinstance(get_action_buttons, (list, tuple)):
                extra_buttons = [Button(**button) for button in get_action_buttons]
            else:
                extra_buttons = [Button(**get_action_buttons)]

        return [btn for btn in extra_buttons + parent_buttons + buttons if self.request.user.has_perm(btn.permission)]

    def get_display_fields(self):
        """
        Retrieves fields to display in the payslip view.

        Returns:
            list: A list of field objects from the PaidEmployee model that are in list_display.
        """
        try:
            model_class = apps.get_model('payroll', 'paidemployee')
            return [field for field in model_class._meta.fields if field.name in model_class.list_display]
        except Exception as e:
            logger.error(f"Error retrieving display fields for PaidEmployee: {str(e)}")
            return []

    def configure_form_fields(self, form):
        """
        Configures form fields to use checkboxes for specific fields.

        Args:
            form: The form instance to configure.

        Returns:
            Form: The configured form instance.
        """
        for field in ['social_security_amount', 'taxable_amount']:
            form.fields[field].widget = CheckboxInput()
            form.fields[field].required = False
        return form

    def get(self, request, pk):
        """
        Handles GET requests by retrieving a PaidEmployee instance, its associated
        ItemPaid objects, and an unbound ItemPaid form.

        Args:
            request (HttpRequest): The incoming GET request.
            pk (int): The primary key of the PaidEmployee object.

        Returns:
            HttpResponse: Rendered template with context.
        """
        try:
            self.kwargs.update({'app': 'payroll', 'model': 'paidemployee'})
            model_class = apps.get_model('payroll', 'paidemployee')
            employee_obj = get_object_or_404(model_class, pk=pk)

            # Optimize queries with select_related and prefetch_related
            items = employee_obj.itempaid_set.all().select_related('employee').order_by('code')
            ItemPaidForm = modelform_factory(
                models.ItemPaid,
                # exclude=[field.name for field in Base._meta.fields] + ['id', 'payslip', 'rate', 'time', 'employee']
            )
            form = self.configure_form_fields(ItemPaidForm())
            action_buttons = self.get_action_buttons(employee_obj)
            display_fields = self.get_display_fields()

            context = {
                'employee_obj': employee_obj,
                'items': items,
                'form': form,
                'action_buttons': action_buttons,
                'display_fields': display_fields,
                'model_class': model_class
            }

            return render(request, self.template_name, context)

        except Exception as e:
            logger.error(f"Error processing GET request for PaidEmployee {pk}: {str(e)}")
            messages.error(request, _("Une erreur est survenue lors du chargement de la fiche de paie."))
            return redirect(self.next or reverse_lazy('core:home'))

    @transaction.atomic
    def post(self, request, pk):
        """
        Handles POST requests to update a PaidEmployee's payroll details by processing
        a submitted ItemPaid form.

        Args:
            request (HttpRequest): The incoming POST request.
            pk (int): The primary key of the PaidEmployee object.

        Returns:
            HttpResponse: Redirect on success, or re-rendered form on failure.
        """
        try:
            self.kwargs.update({'app': 'payroll', 'model': 'paidemployee'})
            model_class = apps.get_model('payroll', 'paidemployee')
            employee_obj = get_object_or_404(model_class, pk=pk)

            # Create form with excluded fields
            ItemPaidForm = modelform_factory(
                models.ItemPaid,
                exclude=[field.name for field in Base._meta.fields] + ['id', 'payslip', 'rate', 'time', 'employee']
            )
            form = self.configure_form_fields(ItemPaidForm(request.POST))

            if not form.is_valid():
                messages.error(request, _('Remplissez correctement le formulaire'))
                items = employee_obj.itempaid_set.all().select_related('employee').order_by('code')
                action_buttons = self.get_action_buttons(employee_obj)
                display_fields = self.get_display_fields()
                return render(request, self.template_name, locals())

            instance = form.save(commit=False)

            # Validate type_of_item
            if not hasattr(instance, 'type_of_item') or instance.type_of_item is None:
                logger.error(f"Invalid type_of_item for ItemPaid instance, pk={pk}")
                messages.error(request, _("Type d'élément invalide."))
                return render(request, self.template_name, locals())

            # Apply business logic for amounts
            instance.amount_qp_employee = abs(instance.amount_qp_employee) * instance.type_of_item
            instance.amount_qp_employer = abs(instance.amount_qp_employer)

            # Handle checkbox fields
            instance.social_security_amount = (
                abs(instance.amount_qp_employee) * instance.type_of_item
                if form.cleaned_data.get('social_security_amount')
                else 0
            )
            instance.taxable_amount = (
                abs(instance.amount_qp_employee) * instance.type_of_item
                if form.cleaned_data.get('taxable_amount')
                else 0
            )

            # Associate with employee and set defaults
            instance.employee = employee_obj
            instance.is_payable = True  # Default: Item is payable
            instance.is_bonus = False  # Default: Item is not a bonus
            instance.save()

            # Update related objects
            employee_obj.update()
            employee_obj.payroll.update()

            messages.success(request, _('L\'élément a été ajouté avec succès'))
            next_url = request.META.get('HTTP_REFERER', self.next or reverse_lazy('core:list', kwargs={
                'app': 'payroll',
                'model': 'paidemployee'
            }))
            return redirect(next_url)

        except Exception as e:
            logger.error(f"Error processing POST request for PaidEmployee {pk}: {str(e)}")
            messages.error(request, _("Une erreur est survenue lors de l'ajout de l'élément."))
            items = employee_obj.itempaid_set.all().select_related('employee').order_by('code') if 'employee_obj' in locals() else []
            return render(request, self.template_name, locals())