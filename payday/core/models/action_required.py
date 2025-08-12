from django.utils.translation import gettext as _
from django.urls import reverse_lazy
from core.models import fields
from datetime import datetime, timezone
from django.apps import apps
from django.db import models
from itertools import chain
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
    def sort_by_created_at_desc(self, data: list[dict]) -> list[dict]:
        def parse_date(item):
            dt = item.get("created_at")
            if not isinstance(dt, datetime):
                return datetime.min.replace(tzinfo=timezone.utc)  # fallback for missing or invalid
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)  # ensure UTC-aware
        return sorted(data, key=parse_date, reverse=True)

    def get_queryset(self):
        """Aggregate and wrap all action-required entries into model instances."""
        models_with_action = filter(
            lambda model: callable(getattr(model, "get_action_required", None)),
            apps.get_models()
        )

        # Efficiently extract, flatten, and discard falsy returns
        flattened_data = chain.from_iterable(
            (result for model in models_with_action if (result := model.get_action_required()))
        )
        flattened_data = list(flattened_data)

        # Instantiate your model with each action payload
        flattened_data = self.sort_by_created_at_desc(flattened_data)
        instances = [self.model(**entry) for entry in flattened_data]
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
    list_display = ['app', 'model', 'title', 'description', 'created_at']


    def get_absolute_url(self):
        model = apps.get_model(self.app, model_name=self.model)
        kwargs = {'app': self.app, 'model': self.model}
        
        obj = getattr(self, 'pk', None) and model.objects.filter(pk=self.pk).first()
        
        if not obj:
            return reverse_lazy("core:list", kwargs=kwargs)

        if hasattr(obj, "get_absolute_url") and callable(obj.get_absolute_url):
            return obj.get_absolute_url()

        kwargs['pk'] = self.pk
        return reverse_lazy("core:change", kwargs=kwargs)

    @staticmethod
    def can_search():
        return False

    def save(self):
        raise NotImplementedError('ActionRequired objects cannot be saved')

    def delete(self):
        raise NotImplementedError('ActionRequired objects cannot be deleted')

    class Meta:
        # managed = False
        verbose_name = _('action requise')
        verbose_name_plural = _('actions requises')
