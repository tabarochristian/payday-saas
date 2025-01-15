from django.utils.translation import gettext as _
from crispy_forms.layout import Layout
from core.models import fields, Base

class Attendance(Base):
    employee = fields.ModelSelectField('employee.Employee', verbose_name=_('employé'), editable=False)
    device = fields.ModelSelectField('employee.Device', verbose_name=_('dispositif'), editable=False)
    checked_at = fields.DateTimeField(verbose_name=_('vérifié à'), editable=False)

    search_fields = ('employee__first_name', 'employee__last_name', 'employee__register_number')
    list_display = ('device', 'employee', 'checked_at')
    list_filter = ('device', 'checked_at',)

    class Meta:
        unique_together = ('employee', 'checked_at')
        verbose_name_plural = _('attendances')
        verbose_name = _('attendance')

    @property
    def name(self):
        return self.employee.name

    def __str__(self):
        return self.employee.name