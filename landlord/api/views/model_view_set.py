from rest_framework.permissions import DjangoModelPermissions
from api.serializers import model_serializer_factory
from rest_framework.viewsets import ModelViewSet
from django.apps import apps

from django.contrib.contenttypes.models import ContentType
from django_filters.rest_framework import DjangoFilterBackend

class ApiViewSet(ModelViewSet):
    permission_classes = [DjangoModelPermissions]
    filter_backends = [DjangoFilterBackend]

    def get_content_type(self):
        app, model = self.kwargs['app'], self.kwargs['model']
        return ContentType.objects.get(app_label=app, model=model)
    
    def get_model(self):
        app, model = self.kwargs['app'], self.kwargs['model']
        return apps.get_model(app, model_name=model)
    
    def get_queryset(self):
        return self.get_model().objects.all()

    def get_serializer_class(self):
        depth = self.request.query_params.get('__depth', 0)
        return model_serializer_factory(self.get_model(), depth=int(depth))