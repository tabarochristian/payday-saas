from django.utils.translation import gettext as _
from django.urls import reverse_lazy
from django.shortcuts import render
from django.apps import apps
from .base import BaseView

from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.apps import apps
from core import views as core_views
from django.http.request import QueryDict

class ActionRequired(core_views.List):
    action = ['view']

    def get_action_buttons(self):
        return []

    def get(self, request):
        self.kwargs.update({'app': 'core', 'model': 'actionrequired'})
        return super().get(request, app='core', model='actionrequired')