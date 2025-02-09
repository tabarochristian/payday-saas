from django.utils.translation import gettext as _
from core.forms import modelform_factory
from crispy_forms.layout import Layout
from django.utils.timezone import now
from core.forms.button import Button
from django.urls import reverse_lazy
from core.views import Change
from django.apps import apps

class Employee(Change):
    template_name = "employee/change.html"

    def get_list_display_fields(self):
        model = apps.get_model('employee', 'employee')
        list_display = getattr(model, 'list_display', [])
        return [field for field in model._meta.fields if field.name in list_display]
    
    def get_missed_value_form(self):
        public_fields = ["spouse", "payment_account", "physical_address", "emergency_information"]
        model = apps.get_model('employee', 'employee')
        obj = model.objects.get(pk=self.kwargs['pk'])
        missed_fields = [field for field in public_fields if not getattr(obj, field)]
        if not missed_fields:
            return None
        modelform = modelform_factory(model, fields=missed_fields, layout=Layout(*missed_fields))
        return modelform()

    def get_action_buttons(self):
        buttons = super().get_action_buttons()
        buttons.insert(0, Button(**{
            'text': _('Imprimer'),
            'tag': 'a',
            'url': reverse_lazy('employee:print', kwargs={'pk': self.kwargs['pk']}),
            'classes': 'btn btn-light-success',
        }))
        return buttons

    def attendancces(self):
        qs = self._get_object().attendance_set.all().attended(
            checked_at__year=now().year
        )
        return list(qs)

    def get(self, request, pk):
        self.kwargs['app'] = 'employee'
        self.kwargs['model'] = 'employee'
        return super().get(request, self.kwargs['app'], self.kwargs['model'], pk)
    
    def post(self, request, pk):
        self.kwargs['app'] = 'employee'
        self.kwargs['model'] = 'employee'
        return super().post(request, self.kwargs['app'], self.kwargs['model'], pk)