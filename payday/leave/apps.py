# from django.utils.translation import gettext as _
from django.apps import AppConfig

def _(value):
    return value

class LeaveConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    verbose_name = _("conge")
    name = "leave"

    def ready(self):
        """Method called when the app is ready."""
        import leave.receivers
