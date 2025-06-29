# from django.utils.translation import gettext as _
from django.apps import AppConfig

def _(value):
    return value

class PayrollConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    verbose_name = _("paie")
    name = 'payroll'
    
    def ready(self):
        import payroll.signals
