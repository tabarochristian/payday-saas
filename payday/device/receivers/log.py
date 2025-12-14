# device/signals.py
from django.db.models.signals import pre_save
from django.dispatch import receiver
from rest_framework.exceptions import ValidationError
from django.contrib.gis.geos import GEOSException

from device.models import Device, Log

METERS_PER_DEGREE = 111_320.0


@receiver(pre_save, sender=Log)
def validate_log_geofence(sender, instance, **kwargs):
    """
    DRF-friendly geofence validation for Log entries.
    Produces clean JSON API errors instead of Django HTML errors.
    """

    # --- 1. Retrieve device ---
    try:
        device = Device.objects.get(sn=instance.sn)
    except Device.DoesNotExist:
        return

    if not device.is_geofence_configured:
        return

    # --- 2. Ensure log has a location ---
    if instance.geofence_center is None:
        raise ValidationError({
            "geofence": (
                f"La localisation est obligatoire pour le terminal '{device.sn}' "
                f"car il est configuré avec une géofence."
            )
        })

    center = device.geofence_center
    point = instance.geofence_center
    radius_m = device.geofence_radius

    # --- 3. Compute distance ---
    try:
        if center.srid == 4326:
            distance_deg = center.distance(point)
            distance_m = distance_deg * METERS_PER_DEGREE
        else:
            distance_m = center.distance(point)

    except GEOSException as e:
        raise ValidationError({"geofence": f"Erreur de calcul géospatial: {e}"})
    except Exception as e:
        raise ValidationError({"geofence": f"Erreur inattendue: {e}"})

    # --- 4. Validate geofence ---
    if distance_m > radius_m:
        raise ValidationError({
            "geofence": (
                f"Le pointage (SN: {device.sn}) est en dehors de la géofence. "
                f"Distance du centre: {distance_m:.2f} m. "
                f"Rayon autorisé: {radius_m} m."
            )
        })
