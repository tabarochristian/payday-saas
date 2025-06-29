from django.utils.translation import gettext as _
from core.forms import modelform_factory
from crispy_forms.layout import Layout
from django.utils.timezone import now
from core.forms.button import Button
from django.urls import reverse_lazy
from core.views import Change
from django.apps import apps


class Employee(Change):
    """Specialized change view for Employee objects with custom behavior."""
    
    template_name = "employee/change.html"

    @property
    def model_class(self):
        """Return the model class from URL kwargs."""
        return apps.get_model("employee", model_name="employee")

    def get_list_display_fields(self):
        """Retrieve fields in `list_display`, preserving their order."""
        model_class = self.model_class
        list_display = getattr(model_class, 'list_display', [])
        fields = {field.name: field for field in model_class._meta.get_fields() if field.name in list_display}
        return [fields[name] for name in list_display if name in fields]  # Preserves order

    def get_missed_value_form(self):
        """Build a dynamic form for public fields missing values."""
        public_fields = ["spouse", "payment_account", "physical_address", "emergency_information"]
        model_class = self.model_class
        try:
            employee_instance = model_class.objects.get(pk=self.kwargs['pk'])
        except model_class.DoesNotExist:
            return None  # Avoids unnecessary queries if employee doesn't exist

        missed_fields = [field for field in public_fields if not getattr(employee_instance, field, None)]
        return modelform_factory(model_class, fields=missed_fields, layout=Layout(*missed_fields)) if missed_fields else None

    def get_action_buttons(self, obj=None):
        """Append a 'Print' button to action buttons dynamically."""
        buttons = super().get_action_buttons()
        print_button = Button(
            tag='a',
            text=_('Imprimer'),
            classes='btn btn-light-success',
            url=reverse_lazy('employee:print', kwargs={'pk': self.kwargs['pk']})
        )
        return [print_button] + buttons  # Inserts at the start efficiently

    def attendances(self):
        """Retrieve attendance records for the current year."""
        return list(self._get_object().attendances().values('checked_at', 'count'))

    def get(self, request, pk):
        """Ensure keyword arguments are correctly set before delegating to parent method."""
        self.kwargs.update({'app': 'employee', 'model': 'employee'})
        return super().get(request, self.kwargs['app'], self.kwargs['model'], pk)

    def post(self, request, pk):
        """Ensure keyword arguments are set before delegating to parent method."""
        self.kwargs.update({'app': 'employee', 'model': 'employee'})
        return super().post(request, self.kwargs['app'], self.kwargs['model'], pk)
