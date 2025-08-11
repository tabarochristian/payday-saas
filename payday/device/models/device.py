from django.utils.translation import gettext as _
from django.utils.html import escapejs
from crispy_forms.layout import Layout
from core.models import fields, Base
from django.db import models
import json

class DeviceStatus(models.TextChoices):
    DISCONNECTED = "disconnected", _("Disconnected")
    CONNECTED = "connected", _("Connected")
    
    
class Device(Base):
    """
    Represents a connected device.
    """
    sn = fields.CharField(_("Serial Number"), max_length=255, unique=True, blank=False, null=False)
    status = fields.CharField(_("Status"), max_length=255, default='disconnected', editable=False)
    name = fields.CharField(_("Device Name"), max_length=255, blank=True, null=True)
    status = None

    list_display = ("id", "name", "sn", "status")
    layout = Layout("sn", "name")
    list_filter = ("status",)

    class Meta:
        verbose_name_plural = _("terminals")
        verbose_name = _("terminal")

    def __str__(self):
        return self.sn

    @property
    def is_connected(self):
        return self.status == DeviceStatus.CONNECTED

    @property
    def is_disconnected(self):
        return self.status == DeviceStatus.DISCONNECTED

    @staticmethod
    def get_action_required(user=None):
        if Device.objects.only("id").exists():
            return []

        return [{
            "app": "device",
            "model": "device",
            "title": _("Aucun appareil trouvé"),
            "description": _("Aucun appareil de pointage trouvé")
        }]