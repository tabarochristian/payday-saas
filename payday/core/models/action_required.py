from crispy_forms.layout import Layout, Column, Row
from django.utils.translation import gettext as _
from django.urls import reverse_lazy
from django.apps import apps
from django.db import models
from django.core.cache import cache
from core.models import fields
from .base import Base

class ActionRequiredList(list):
    model = 'actionrequired'
    
    def __init__(self, *args):
        super().__init__(*args)

    def select_related(self, *args):
        """Placeholder for select_related logic."""
        return self

    def prefetch_related(self, *args):
        """Placeholder for prefetch_related logic."""
        return self

    def filter(self, *args, **kwargs):
        """Implement filtering logic if needed."""
        return self

    def order_by(self, *args):
        """Implement ordering logic if needed."""
        return self

    def count(self):
        """Return the count of items."""
        return len(self)

class ActionRequiredManager(models.Manager):
    def cache_queryset(self):
        """Apply the business logic to fetch the action required."""
        models_with_action_required = [model for model in apps.get_models() if hasattr(model, 'get_action_required')]
        
        data = []
        for model in models_with_action_required:
            actions = model.get_action_required()
            if actions:
                data.extend(actions)

        # Cache the data for better performance (cache it for 10 minutes)
        try:
            cache.set('action_required_data', data, timeout=600)
        except Exception as e:
            print(f"Error caching data: {e}")
        return data

    def get_queryset(self):
        """Return the cached or freshly generated queryset."""
        cache_key = 'action_required_data'
        data = cache.get(cache_key)

        if data is None:
            data = self.cache_queryset()
        
        # Convert the data into instances of the model
        instances = [self.model(**item) for item in data]
        return ActionRequiredList(instances)

class ActionRequired(Base):
    app = fields.CharField(_('application'), max_length=255)
    model = fields.CharField(_('modèle'), max_length=255)
    title = fields.CharField(_('titre'), max_length=255)
    description = fields.TextField(_('description'))

    @property
    def name(self):
        return self.title

    objects = ActionRequiredManager()
    list_display = ['app', 'model', 'title', 'description']

    def get_absolute_url(self):
        return reverse_lazy('core:list', kwargs={'app': self.app, 'model': self.model})

    @staticmethod
    def can_search():
        return False

    class Meta:
        managed = False
        verbose_name = _('action requise')
        verbose_name_plural = _('actions requises')
