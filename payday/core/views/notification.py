from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.apps import apps
from core import views as core_views
from django.http.request import QueryDict

class Notifications(core_views.List):
    action = ['view']

    def get_action_buttons(self):
        return []

    def get_list_display(self):
        model = self.get_model()
        list_display = ['actor', 'verb', 'description', 'unread', 'timestamp']
        list_display_order = {field:i for i, field in enumerate(list_display)}
        return sorted([field for field in model._meta.fields 
                       if field.name in list_display], key=lambda field: list_display_order[field.name])

    def get_list_filter(self):
        return ['unread', 'public']

    def get(self, request):
        query = {"recipient_id": request.user.pk}
        self.kwargs.update({'app': 'notifications', 'model': 'notification'})
        request.GET = QueryDict("&".join([f"{key}={value}" for key, value in query.items()]))
        return super().get(request, app='notifications', model='notification')