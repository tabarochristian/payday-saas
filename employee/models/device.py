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
    branch = fields.ModelSelectField('employee.branch', verbose_name=_("site"), blank=True, null=True)
    sn = fields.CharField(_("Serial Number"), max_length=255, unique=True, editable=False)
    name = fields.CharField(_("Device Name"), max_length=255, blank=True, null=True)

    list_filter = ("status",)
    list_display = ("name", "sn", "status")
    layout = Layout("branch", "name", "_metadata")

    def get_action_buttons(self):
        host = "localhost"
        return [
            {
                'tag': 'button',
                'text': _('Actualiser'),
                'classes': 'btn btn-light-success ajax-request',
                'attrs': {
                    'data-url': "http://localhost:7788/send-command",
                    'data-method': "POST",
                    'data-json': escapejs(json.dumps({
                        "cmd": "getnewlog",
                        "stn": True,
                    })),
                }
            },
        ]

    class Meta:
        verbose_name_plural = _("terminals")
        verbose_name = _("terminal")

    def __str__(self):
        return self.sn

    def save(self, *args, **kwargs):
        if not self.name:
            self.name = self.sn
        super().save(*args, **kwargs)

    @property
    def is_connected(self):
        return self.status == DeviceStatus.CONNECTED

    @property
    def is_disconnected(self):
        return self.status == DeviceStatus.DISCONNECTED