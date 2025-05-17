from django.utils.translation import gettext as _
from django.db.models import UniqueConstraint
from core.models import fields, Base
from django.db import models
import json
    
class Log(Base):
    """
    Stores attendance logs from a connected attendance device.
    """

    sn = models.CharField(_("Serial Number"), max_length=255, db_index=True)
    timestamp = models.DateTimeField(_("Timestamp"))
    enroll_id = models.IntegerField(_("Enroll ID"))  # User ID
    
    mode = models.IntegerField(_("Verification Mode"), choices=[
        (0, _("Fingerprint")),
        (1, _("Card")),
        (2, _("Password")),
        (8, _("Face"))
    ])
    in_out = models.IntegerField(_("Entry Type"), choices=[(0, _("In")), (1, _("Out"))])
    event = models.IntegerField(_("Event Type"))

    verify_mode = models.IntegerField(_("Verify Mode"), blank=True, null=True)
    temperature = models.FloatField(_("Temperature"), blank=True, null=True)  # Optional for some devices
    image = models.TextField(_("Punch Image"), blank=True, null=True)  # Base64 encoded image
    
    class Meta:
        unique_together = ("sn", "timestamp", "enroll_id", "in_out")
        verbose_name_plural = _("Logs")
        verbose_name = _("Log")
        indexes = [
            models.Index(fields=["sn", "timestamp"])
        ]
        constraints = [
            UniqueConstraint(fields=["sn", "timestamp", "enroll_id", "in_out"], name="unique_attendance_log")
        ]
