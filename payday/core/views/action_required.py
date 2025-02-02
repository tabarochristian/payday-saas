from django.utils.translation import gettext as _
from django.urls import reverse_lazy
from django.shortcuts import render
from django.apps import apps
from .base import BaseView


class ActionRequired(BaseView):
    template_name = 'required.html'

    def devices(self, qs):
        model = apps.get_model('employee', 'device')
        device = model.objects.all().exists()
        if device: return qs
        qs.insert(0, {
            'created_by': None, 'created_at': None,
            'url': reverse_lazy('core:list', args=['employee', 'device']),

            'pk': 1,
            'app': 'employee',
            'model': 'device',
            'model_verbose': _('Terminal de presence'),
            'description': _('Aucun terminal de presence n\'a été detecté'),
        })
        return qs

    def get(self, request):
        qs = []
        qs = self.devices(qs)
        return render(request, self.template_name, locals())