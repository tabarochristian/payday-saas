from django.contrib.gis.db import models as gis_models
from django.utils.translation import gettext as _
from django.db.models import UniqueConstraint
from django.db import models
from core.models import Base
    
class Log(Base):
    """
    Stores attendance logs from a connected attendance device.
    """

    sn = models.CharField(_("Serial Number"), max_length=255, db_index=True)
    timestamp = models.DateTimeField(_("Timestamp"))
    enroll_id = models.IntegerField(_("Enroll ID"))  # User ID
    status = None
    
    mode = models.IntegerField(_("Verification Mode"), choices=[
        (0, _("Fingerprint")),
        (1, _("Card")),
        (2, _("Password")),
        (8, _("Face")),
        (10, _("Web")),
    ])
    in_out = models.IntegerField(_("Entry Type"), choices=[(0, _("In")), (1, _("Out"))])
    event = models.IntegerField(_("Event Type"))

    verify_mode = models.IntegerField(_("Verify Mode"), blank=True, null=True)
    temperature = models.FloatField(_("Temperature"), blank=True, null=True)  # Optional for some devices
    image = models.TextField(_("Punch Image"), blank=True, null=True)  # Base64 encoded image

    geofence_center = gis_models.PointField(
        verbose_name=_("Centre de la Géofence"),
        help_text=_("Coordonnées (Longitude, Latitude) du centre de la zone de pointage."),
        geography=True,
        default=None,
        null=True,
        blank=True # Added blank=True for consistency if null is allowed
    )

    list_display = ('sn', 'timestamp', 'in_out', 'enroll_id', 'created_at')
    
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
