# app/signals.py
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
# Import D for the Distance object (cleanest way to work with meters)
from django.contrib.gis.measure import D 

from device.models import Device, Log 


@receiver(pre_save, sender=Log)
def validate_log_geofence(sender, instance, **kwargs):
    """
    Checks if a Log entry's location falls within the geofence 
    defined by the associated Device (if one exists).
    """
    
    # 1. Retrieve the Device associated with the Log's serial number (sn)
    try:
        device = Device.objects.get(sn=instance.sn)
    except Device.DoesNotExist:
        # If the Device doesn't exist, we cannot enforce the geofence rule. 
        # The log is saved without location validation.
        return

    # 2. Check if the Device has a geofence configured
    if not device.is_geofence_configured:
        # Geofence validation is not required for this device.
        return

    # 3. Check for Log location data
    if instance.geofence_center is None:
        # A geofence exists for the device, but the log has no location data.
        raise ValidationError(
            f"La localisation est **obligatoire** pour le terminal '{device.sn}' car il est configuré avec une géofence."
        )

    # 4. Perform the Geofence Validation
    
    # Get the device's geofence center and radius
    geofence_radius_m = device.geofence_radius
    log_location = instance.geofence_center
    center_point = device.geofence_center

    # Calculate the distance between the log location and the device's center point.
    # The .distance() method returns a Distance object.
    # 
    distance_object = center_point.distance(log_location)
    
    # We use the .m property of the Distance object to get the distance in meters.
    distance_in_meters = distance_object.m
    
    # Check if the log is outside the allowed radius
    if distance_in_meters > geofence_radius_m:
        # Distance is greater than the allowed radius: Raise Validation Error
        raise ValidationError(
            f"Le pointage (SN: {device.sn}) est en dehors de la zone de géofence. "
            f"Distance du centre: **{distance_in_meters:.2f}m**. "
            f"Rayon maximum autorisé: **{geofence_radius_m}m**."
        )
        
    # If the distance is less than or equal to the radius, the log is valid.

# Remember to ensure this signals file is imported in your app's AppConfig.ready() method.