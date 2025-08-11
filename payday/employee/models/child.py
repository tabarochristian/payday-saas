from crispy_forms.layout import Layout
from core.models import Base, fields
from .employee import Employee

from django.utils.translation import gettext as _
from django.db import models


class Child(Base):
    employee = fields.ModelSelectField(Employee, verbose_name=_('employé'), null=True, on_delete=models.SET_NULL)
    full_name = fields.CharField(verbose_name=_('nom complet'), max_length=100, inline=True)
    date_of_birth = fields.DateField(verbose_name=_('date de naissance'), inline=True)
    status = None

    list_display = ('id', 'employee', 'full_name', 'date_of_birth')
    search_fields = ('employee__registration_number', 'full_name') 
    layout = Layout(
        'full_name',
        'date_of_birth',
    )
    list_filter = ('employee__registration_number', 'employee__status', 'date_of_birth')

    @property
    def name(self):
        return self.full_name

    class Meta:
        verbose_name = _('enfant')
        verbose_name_plural = _('enfants')
