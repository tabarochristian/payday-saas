from django.shortcuts import render, redirect, get_object_or_404
from django.utils.translation import gettext as _
from django.contrib import messages
from django.urls import reverse_lazy
from django.apps import apps
from core.forms import modelform_factory
from core.forms.button import Button
from core.views import Change
from payroll import models
from core.models import Base
from django.forms import CheckboxInput


class Payslip(Change):
    """
    A view for updating (changing) payroll data related to a specific paid employee,
    with additional functionality to view the corresponding payslip.

    This view extends the base Change view and customizes action buttons, GET, and POST
    handling for Employee payroll items.
    """
    template_name = "payroll/payslip.html"

    def get_model(self):
        """
        Returns the Payslip model.

        Returns:
            Model: The Payslip model from the payroll app.
        """
        return apps.get_model('payroll', model_name='paidemployee')

    def get_action_buttons(self):
        """
        Generate and return the list of action buttons for the payslip view.

        It starts with the action buttons from the base Change view (after removing the
        last two default buttons) and adds a custom Print button that links to the 
        payslip view.
        
        Returns:
            list: A list of Button objects filtered by user permissions.
        """
        # Retrieve the primary key from URL kwargs and set application-specific values.
        pk = self.kwargs.get('pk')
        app = 'payroll'
        model = 'payslip'

        # Get the default action buttons from the parent view and remove the last two.
        base_buttons = super().get_action_buttons()[:-2]
        # Add a custom button for printing the payslip.
        print_button = Button(**{
            'tag': 'a',
            'text': _('Bulletin de paie'),
            'url': reverse_lazy('payroll:slips') + f"?pk={pk}",
            'classes': 'btn btn-light-primary',
        })
        buttons = base_buttons + [print_button]
        # Filter out buttons based on user permissions.
        return [button for button in buttons if self.request.user.has_perm(button.permission)]

    def get_display_fields(self):
        """
        Generate and return a list of fields to display in the payslip view.

        It retrieves the fields from the Base model and the associated ItemPaid model.
        
        Returns:
            list: A list of field names to display in the template.
        """
        # Retrieve the fields from the Base model and the associated ItemPaid model.
        model_class = apps.get_model('payroll', 'paidemployee')
        return [field for field in model_class._meta.fields if field.name in model_class.list_display]

    def get(self, request, pk):
        """
        Handle GET requests by retrieving an Employee (paidemployee) instance,
        its associated payroll items (ItemPaid), and initializing an unbound form for ItemPaid.
        
        Args:
            request (HttpRequest): The incoming GET request.
            pk (int): The primary key of the paidemployee object.
            
        Returns:
            HttpResponse: Rendered template with context containing the object, items, and form.
        """
        # Set the URL kwargs for the payroll app and paidemployee model.
        self.kwargs.update({'app': 'payroll', 'model': 'paidemployee'})
        model_class = apps.get_model('payroll', 'paidemployee')
        # Retrieve the paid employee instance.
        employee_obj = get_object_or_404(model_class, pk=pk)
        # Retrieve the related ItemPaid objects, ordered by 'code'.
        items = employee_obj.itempaid_set.all().order_by('code')
        # Build an unbound form for ItemPaid using all fields.
        ItemPaidForm = modelform_factory(models.ItemPaid, fields='__all__')
        form = ItemPaidForm()

        # Set the form fields to display as checkboxes.
        for field in ['social_security_amount', 'taxable_amount']:
            form.fields[field].widget = CheckboxInput()
            form.fields[field].required = False

        return render(request, self.template_name, locals())
    
    def post(self, request, pk):
        """
        Handle POST requests to update a paid employee's payroll details by processing 
        the submitted form for an associated ItemPaid record.
        
        The method validates the form, applies business logic to adjust numerical values,
        saves the instance, updates related objects, and then redirects back to the referring URL.
        
        Args:
            request (HttpRequest): The incoming POST request.
            pk (int): The primary key of the paidemployee object.
            
        Returns:
            HttpResponseRedirect: A redirect to the previous page on success, or re-rendering of 
            the form on failure.
        """
        # Set the URL kwargs for the payroll app and paidemployee model.
        self.kwargs.update({'app': 'payroll', 'model': 'paidemployee'})
        model_class = apps.get_model('payroll', 'paidemployee')
        employee_obj = get_object_or_404(model_class, pk=pk)
        
        # Determine fields to exclude based on the Base model and additional ones.
        base_fields = [field.name for field in Base._meta.fields] + ['id', 'payslip', 'rate', 'time']
        # Optionally, you can compute included fields; the current code does not use it
        # since fields='__all__' is provided in the form factory below.
        form_class = modelform_factory(models.ItemPaid, fields='__all__')
        form = form_class(request.POST)

        # Set the form fields to display as checkboxes.
        for field in ['social_security_amount', 'taxable_amount']:
            form.fields[field].widget = CheckboxInput()
            form.fields[field].required = False

        # Validate the form and display a warning message if it is not valid.
        if not form.is_valid():
            messages.warning(request, _('Remplissez correctement le formulaire'))
            return render(request, self.template_name, locals())
        
        instance = form.save(commit=False)

        # Apply business logic to update numeric values based on the type of item.
        instance.amount_qp_employee = abs(instance.amount_qp_employee) * instance.type_of_item
        instance.amount_qp_employer = abs(instance.amount_qp_employer)

        # check if the social_security_amount and taxable_amount are checked
        if instance.social_security_amount:
            instance.social_security_amount = abs(instance.amount_qp_employee) * instance.type_of_item

        if instance.taxable_amount:
            instance.taxable_amount = abs(instance.amount_qp_employee) * instance.type_of_item
        
        # Associate the new ItemPaid instance with the employee.
        instance.employee = employee_obj
        # Set default values.
        instance.is_payable = True
        instance.is_bonus = False
        instance.save()

        # Update related objects.
        employee_obj.update()
        employee_obj.payroll.update()

        messages.success(request, _('L\'élément a été ajouté avec succès'))
        next_url = request.META.get('HTTP_REFERER')
        return redirect(next_url)
