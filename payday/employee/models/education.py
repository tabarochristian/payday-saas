from core.utils import upload_directory_file
from crispy_forms.layout import Layout
from core.models import Base, fields
from .employee import Employee

from django.utils.translation import gettext as _
from django.db import models

class Education(Base):
    employee = fields.ModelSelectField(Employee, verbose_name=_('employé'), null=True, on_delete=models.SET_NULL)

    institution = fields.CharField(_('institution'), max_length=255, inline=True)
    degree = fields.CharField(_('diplôme'), max_length=255, inline=True)

    start_date = fields.DateField(_('date de début'), null=True, blank=True, inline=True)
    end_date = fields.DateField(_('date de fin'), null=True, blank=True, inline=True)

    list_display = ('id', 'employee', 'institution', 'degree', 'start_date', 'end_date')
    layout = Layout(
        'employee',
        'institution',
        'degree',
        'start_date',
        'end_date'
    )

    class Meta:
        verbose_name = _('education')
        verbose_name_plural = _('educations')
