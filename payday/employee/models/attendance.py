from employee.models.managers import AttendanceManager
from django.utils.translation import gettext as _
from django.contrib.auth import get_user_model
from crispy_forms.layout import Layout
from core.models import fields, Base
from django.urls import reverse_lazy
from django.db import models

from django.contrib.contenttypes.fields import GenericForeignKey

class Attendance(Base):
    device = fields.ModelSelectField('device.Device', verbose_name=_('dispositif'), blank=True, null=True, on_delete=models.DO_NOTHING)
    employee = fields.ModelSelectField('employee.Employee', verbose_name=_('employé'), null=True, on_delete=models.DO_NOTHING)
    
    checked_at = fields.DateTimeField(verbose_name=_('vérifié à'))
    count = fields.IntegerField(verbose_name=_("presence"))

    search_fields = ('employee__first_name', 'employee__last_name', 'employee__register_number')
    list_display = ('device', 'employee', 'checked_at')
    list_filter = ('device', 'checked_at')

    layout = Layout(
        'checked_at',
        'employee',
        'device',
    )

    objects = AttendanceManager()

    class Meta:
        unique_together = ('employee', 'checked_at')
        verbose_name_plural = _('presences')
        db_table = 'employee_attendance'
        verbose_name = _('presence')
        managed = False

    @property
    def name(self):
        return f"{self.employee.name} - {self.checked_at}"

    def get_absolute_url(self):
        return reverse_lazy("core:change", kwargs={'app': 'employee', 'model': 'employee', 'pk': self.employee.pk})
    
    def __str__(self):
        return self.employee.name