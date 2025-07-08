from crispy_forms.layout import Layout, Column, Row
from django.utils.translation import gettext as _

from django.core.cache import cache
from core.models import fields
from .base import Base

PREFERENCES = [
    ('DEFAULT_USER_ROLE:STR', _('DEFAULT_USER_ROLE:STR')),
    ('DEFAULT_USER_PASSWORD:STR', _('DEFAULT_USER_PASSWORD:STR')),
    ('DEFAULT_CHECK_IN_RANGE:LIST', _('DEFAULT_CHECK_IN_RANGE:LIST')),
    ('DEFAULT_CHECK_OUT_RANGE:LIST', _('DEFAULT_CHECK_OUT_RANGE:LIST')),
]

class Preference(Base):
    key = fields.CharField(
        verbose_name=_('clé'),
        max_length=100,
        unique=True,
        choices=PREFERENCES
    )

    value = fields.CharField(
        verbose_name=_('valeur'),
        max_length=100
    )

    list_display = ('id', 'key', 'value')
    search_fields = ('key', 'value')
    layout = Layout(
        Row(
            Column('key'),
            Column('value')
        ),
        # '_metadata'
    )

    @property
    def name(self):
        return self.key

    @staticmethod
    def get(key, default=None):
        if preference := Preference.objects.filter(key=key).first():
            return preference.value
        return default

    def save(self, *args, **kwargs):
        self.key = self.key.upper()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _('préférence')
        verbose_name_plural = _('préférences')