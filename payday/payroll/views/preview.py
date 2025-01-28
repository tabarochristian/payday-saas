from django.shortcuts import render, get_object_or_404
from django.utils.translation import gettext as _
from django.core.paginator import Paginator
from django.db.models import Sum
from core.views import Change

from payroll.filters import PayslipFilter
from employee.models import Employee
from django.apps import apps


class Preview(Change):
    template_name = 'payroll/preview.html'

    def get_action_buttons(self):
        buttons = super().get_action_buttons()
        buttons.pop(len(buttons) - 1)
        return buttons
    
    def get(self, request, pk):
        app, model = 'payroll', 'payroll'
        self.kwargs['app'], self.kwargs['model'] = app, model
        app, model = 'payroll', apps.get_model('payroll', 'payroll')
        obj = get_object_or_404(model, pk=pk)
        
        qs = Employee.objects.all()

        return render(request, self.template_name, locals())