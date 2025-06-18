from crispy_forms.layout import Layout, Column, Row
from django.utils.translation import gettext as _
from django.urls import reverse_lazy
from core.models import fields
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

        # Instantiate your model with each action payload
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
    list_display = ['app', 'model', 'title', 'description']


    def get_absolute_url(self):
        url_name = 'core:change' if getattr(self, 'pk', None) else 'core:list'
        kwargs = {'app': self.app, 'model': self.model}
        if url_name == 'core:change':
            kwargs['pk'] = self.pk
        return reverse_lazy(url_name, kwargs=kwargs)


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
