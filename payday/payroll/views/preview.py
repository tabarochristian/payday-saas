from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.utils.translation import gettext as _
from django.contrib import messages
from django.urls import reverse_lazy
from django.apps import apps

from core.forms.button import Button
from core.views import Change

# Constants for payroll statuses
PAYROLL_STATUSES = (
    "IN_PROGRESS",
    "COMPLETED",
    "ERROR"
)

class Preview(Change):
    """
    A view to preview payroll operations before finalizing the payslip process.

    This view renders a preview page for a payroll instance. If the payroll
    has already been processed (its status is within PAYROLL_STATUSES), the user
    is redirected to the payslips view. Otherwise, the view estimates the duration
    required to process the payroll and renders a preview page with action buttons.
    """
    template_name = 'payroll/preview.html'

    def get_model(self):
        return apps.get_model('payroll', model_name='payroll')

    def get_action_buttons(self):
        """
        Construct and return the list of action buttons for the preview page.

        This method modifies the inherited action buttons by removing the last two
        default buttons and adding a custom button that allows the user to 
        "Commencer la paie" (start the payroll processing).

        Returns:
            list: A list of Button objects configured with appropriate tags, URLs, classes, and permissions.
        """
        # Retrieve keyword arguments.
        kwargs = self.kwargs
        # Get the base action buttons from the parent Change view.
        buttons = super().get_action_buttons()
        # Remove the last two default buttons (using negative slicing for clarity).
        buttons = buttons[:-2]

        # Define a custom "Start Payroll" (Commencer la paie) button.
        start_payroll_button = Button(
            tag='button',
            classes='btn btn-success',
            text=_('Commencer la paie'),
            permission=f'{kwargs["app"]}.change_{kwargs["model"]}',
            attrs={
                'type': 'submit',
                'form': f'form-{kwargs["model"]}',
                'name': 'status',
                'value': 'IN_PROGRESS',
            }
        )
        buttons.append(start_payroll_button)
        return buttons

    def estimate_duration(self, queryset, payroll_obj):
        """
        Estimate the duration needed for payroll processing based on the number of items.

        It retrieves the total count of items from two models (item and legalitem) and
        multiplies it by the count of paid employee records (from the queryset) with a constant factor.

        Args:
            queryset (QuerySet): Queryset containing paid employee records.
            payroll_obj: The payroll instance.

        Returns:
            timedelta: A timedelta object representing the estimated processing duration.
        """
        # Retrieve the item models.
        item_model = apps.get_model('payroll', 'item')
        legal_item_model = apps.get_model('payroll', 'legalitem')
        # Compute the total count of items from both models.
        total_items = item_model.objects.count() + legal_item_model.objects.count()
        # Multiply total items by the number of paid employees and constant factor (3ms).
        return timedelta(milliseconds=total_items * queryset.count() * 3)

    def get(self, request, pk):
        """
        Handle GET requests to preview a payroll instance.

        The method performs the following steps:
          1. Sets the view's app/model keyword arguments appropriately.
          2. Retrieves the payroll object for the given primary key.
          3. Retrieves the related paid employee records.
          4. If the payroll status indicates it is already processed, redirects the user to the payslips view.
          5. Otherwise, estimates the processing duration and renders the preview template.

        Args:
            request (HttpRequest): The incoming GET request.
            pk (int): The primary key of the payroll instance.

        Returns:
            HttpResponse: The rendered preview page.
        """
        # Set URL kwargs for the payroll model.
        app = 'payroll'
        self.kwargs.update({'app': 'payroll', 'model': 'payroll'})
        model_class = apps.get_model('payroll', 'payroll')
        payroll_obj = get_object_or_404(model_class, pk=pk)

        # Retrieve all related paid employee records.
        paid_employee_model = apps.get_model('payroll', 'paidemployee')
        paid_employees_qs = paid_employee_model.objects.filter(payroll=payroll_obj)

        # If payroll status is already set (i.e., processed/stopped), redirect.
        if payroll_obj.status in PAYROLL_STATUSES:
            return redirect('payroll:payslips', pk=pk)

        # Estimate the processing duration for the payroll.
        action_buttons = self.get_action_buttons()
        estimation_duration = self.estimate_duration(paid_employees_qs, payroll_obj)
        return render(request, self.template_name, locals())

    def post(self, request, pk):
        """
        Handle POST requests to update the payroll status and trigger payroll processing.

        The method changes the payroll status if specified in the POST data (and valid),
        logs the change, and then triggers the payroll processing via a background task.

        Args:
            request (HttpRequest): The incoming POST request.
            pk (int): The primary key of the payroll instance to update.

        Returns:
            HttpResponseRedirect: A redirect to the payslips view.
        """
        # Set URL kwargs for the payroll model.
        app = 'payroll'
        self.kwargs.update({'app': 'payroll', 'model': 'payroll'})
        model_class = apps.get_model('payroll', 'payroll')
        payroll_obj = get_object_or_404(model_class, pk=pk)

        # Retrieve POST data and determine the requested status.
        data = request.POST.dict()
        status = data.get('status')
        if status and status in PAYROLL_STATUSES:
            messages.success(request, _('La paie a commencé'))
            payroll_obj.status = status
            payroll_obj.save()

        # Trigger payroll processing using a background task.
        from payroll.tasks import Payer
        
        schema = request.get_host().split('.')[0]
        Payer().run(schema, pk)
        # Payer().delay(host[0], pk)

        # Redirect to the payslips view.
        return redirect('payroll:payslips', pk=pk)
