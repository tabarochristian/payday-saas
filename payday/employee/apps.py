# from django.utils.translation import gettext as _
from django.apps import AppConfig

def _(value):
    return value

class EmployeeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    verbose_name = _('employee')
    name = 'employee'

    def ready(self):
        import employee.signals
