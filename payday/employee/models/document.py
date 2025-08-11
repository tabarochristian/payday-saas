from core.utils import upload_directory_file
from crispy_forms.layout import Layout
from core.models import Base, fields
from .employee import Employee

from django.utils.translation import gettext as _
from django.db import models

class Document(Base):
    employee = fields.ModelSelectField(Employee, verbose_name=_('employé'), null=True, on_delete=models.SET_NULL)
    document = fields.FileField(verbose_name=_('nom du document'), upload_to=upload_directory_file, inline=True)
    name = fields.CharField(verbose_name=_('nom du document'), max_length=100, inline=True)
    status = None

    list_display = ('id', 'employee', 'name', 'document')
    layout = Layout(
        'employee',
        'document',
        'name',
    )

    class Meta:
        verbose_name = _('document')
        verbose_name_plural = _('documents')
