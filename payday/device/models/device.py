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
    status = fields.CharField(_("Status"), max_length=255, choices=DeviceStatus.choices, default=DeviceStatus.DISCONNECTED, editable=False)
    # branch = fields.ModelSelectField('employee.branch', verbose_name=_("site"), blank=True, null=True)
    sn = fields.CharField(_("Serial Number"), max_length=255, unique=True, blank=False, null=False)
    name = fields.CharField(_("Device Name"), max_length=255, blank=True, null=True)

    list_display = ("id", "branch", "name", "sn", "status")
    layout = Layout("branch", "sn", "name")
    list_filter = ("status", "branch")

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
    def get_action_required():
        messages = []
        qs = Device.objects.all()
        return [{
            "app": "employee",
            "model": "device",
            "title": _("No device found"),
            "description": _("You need to add a device to the system.")
        }] if not qs.exists() else []