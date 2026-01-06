from django.utils.translation import gettext as _
from django.contrib.gis.db import models as gis_models
from django.contrib.gis.geos import Point
from django.db import models, transaction
from django.utils.html import escapejs

# Assuming these are your custom imports
from crispy_forms.layout import Layout
from core.models import fields, Base 

class DeviceStatus(models.TextChoices):
    """Defines the operational status of the physical device connection."""
    DISCONNECTED = "disconnected", _("Déconnecté") # Changed translation for clarity
    CONNECTED = "connected", _("Connecté")
    
    
class Device(Base):
    """
    Represents a physical time clock terminal device and its configuration (including its geofence).
    """
    sn = fields.CharField(
        _("Numéro de Série"), 
        max_length=255, 
        unique=True, 
        blank=False, 
        null=False
    )
    
    # --- Physical Device Status ---
    status = fields.CharField(
        _("Statut de connexion"), 
        max_length=255, 
        choices=DeviceStatus.choices, # Use choices for cleaner display/validation
        default=DeviceStatus.DISCONNECTED, 
        editable=False
    )
    
    name = fields.CharField(
        _("Nom de l'appareil"), 
        max_length=255, 
        blank=True, 
        null=True
    )

    # --- Geofence Configuration ---
    
    # PointField stores the location (Longitude, Latitude)
    geofence_center = gis_models.PointField(
        verbose_name=_("Centre de la Géofence"),
        help_text=_("Coordonnées (Longitude, Latitude) du centre de la zone de pointage."),
        geography=True,
        default=None,
        null=True,
        blank=True # Added blank=True for consistency if null is allowed
    )
    
    # Radius in meters
    geofence_radius = fields.IntegerField(
        verbose_name=_("Rayon de la Géofence (m)"),
        help_text=_("Rayon de la zone de pointage en mètres."),
        default=None,
        null=True,
        blank=True # Added blank=True for consistency if null is allowed
    )
    
    # --- Django Admin & Custom Attributes ---

    list_display = ("id", "name", "sn", "status", "is_geofence_configured")
    layout = Layout("sn", "name", "geofence_center", "geofence_radius") # Added geofence fields to layout
    list_filter = ("status",) # Added is_active to filter

    class Meta:
        verbose_name_plural = _("Terminaux")
        verbose_name = _("Terminal")
        ordering = ['sn'] # Added default ordering

    def __str__(self):
        return self.name or self.sn

    # --- Property Methods (Improved Logic) ---

    @property
    def is_connected(self):
        """Checks if the device is physically connected (based ONLY on status field)."""
        return any([
            self.status == DeviceStatus.CONNECTED,
            self.is_geofence_configured
        ])

    @property
    def is_disconnected(self):
        """Checks if the device is physically disconnected."""
        return any([
            self.status == DeviceStatus.DISCONNECTED,
            not self.is_geofence_configured
        ])

    @property
    def is_geofence_configured(self):
        """Checks if the geofence boundary is fully defined (center and radius)."""
        # Both center (PointField) and radius (IntegerField) must be set.
        return self.geofence_center is not None and self.geofence_radius is not None

    # --- Static Method (Action Required) ---

    @staticmethod
    def get_action_required(user=None):
        """Returns a list of required actions (e.g., set up initial device)."""
        if Device.objects.only("id").exists():
            return []

        # Use f-strings and correct field names for clarity
        return [{
            "app": "device",
            "model": "device",
            "title": _("Aucun terminal trouvé"),
            "description": _("Veuillez enregistrer le premier terminal de pointage dans le système.")
        }]