from django.utils.translation import gettext as _
from .sub_direction import SubDirection

from crispy_forms.layout import Layout, Row, Column
from django.db import models

from core.models import fields
from core.models import Base

class Service(Base):
    subdirection = fields.ModelSelectField(SubDirection, verbose_name=_('sous-direction'), on_delete=models.CASCADE)
    name = fields.CharField(verbose_name=_('nom'), max_length=100, unique=True)
    status = None

    search_fields = ('subdirection', 'name')
    list_display = ('id', 'subdirection', 'name')
    list_filter = ('subdirection',)
    
    layout = Layout(
        Row(
            Column('subdirection'),
            Column('name')
        ),
    )

    def save(self, *args, **kwargs):
        self.name = self.name.upper()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _('service')
        verbose_name_plural = _('services')
