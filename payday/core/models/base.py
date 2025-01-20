from django_currentuser.db.models import CurrentUserField
from simple_history.models import HistoricalRecords
from django.utils.translation import gettext as _
from crispy_forms.layout import Layout
from django.urls import reverse_lazy
from django.db import models

from api.serializers import model_serializer_factory
from core.utils import DictToObject
from core.models import fields

class Base(models.Model):
    #history = HistoricalRecords(
    #    verbose_name=_('historique'),
    #    verbose_name_plural=_('historiques')
    #)

    _metadata = fields.JSONField(
        verbose_name=_('metadata'), 
        default=dict, 
        blank=True
    )

    updated_by = CurrentUserField(
        verbose_name=_('mis à jour par'), 
        related_name='%(app_label)s_%(class)s_updated_by', 
        on_update=True,
        editable=False
    )
    created_by = CurrentUserField(
        verbose_name=_('créé par'), 
        related_name='%(app_label)s_%(class)s_created_by',
        editable=False
    )

    updated_at = fields.DateTimeField(
        verbose_name=_('mis à jour le/à'), 
        auto_now=True,
        editable=False
    )
    created_at = fields.DateTimeField(
        verbose_name=_('créé le/à'), 
        auto_now_add=True,
        editable=False
    )

    list_display = ('id', 'name')
    search_fields = ('id',)
    layout = Layout()
    list_filter = ()

    @property
    def get_action_buttons(self):
        return list()

    @property
    def serialized(self):
        serializer = model_serializer_factory(self._meta.model)
        return serializer(self).data

    @property
    def metadata(self):
        return DictToObject(self._metadata)

    def get_absolute_url(self):
        return reverse_lazy('core:change', args=[self._meta.app_label, self._meta.model_name, self.pk])

    def __str__(self):
        return str(self.name) if self.name else super().__str__()

    class Meta:
        abstract = True
