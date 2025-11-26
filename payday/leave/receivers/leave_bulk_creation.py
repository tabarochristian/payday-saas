from django.dispatch import receiver
from django.db import transaction
from core.signals import pre_bulk_save
from leave.models import Leave

# Use a specific and descriptive function name
@receiver(pre_bulk_save, sender=Leave)
def set_leave_days_from_duration(sender, instances, **kwargs):
    """
    Sets the 'number_of_days' field on Leave instances based on the 
    'duration' field before bulk saving.
    
    This receiver runs *before* bulk_create, allowing modification of instances 
    that will be used to generate the final SQL INSERT statement.
    """
    
    if not instances:
        return # Exit early if the list is empty

    # 1. Use the 'action' argument if your dispatcher provides it 
    # (recommended for security/logging)
    # if action == 'update':
    #     # Example: If updating, maybe you don't want to re-calculate duration
    #     return 

    # 2. Add validation/type checking for robustness
    if not isinstance(instances, (list, tuple)):
        # Handle cases where the dispatcher might pass something else, 
        # though it should be a list/tuple of objects.
        return 

    # 3. Optimize loop logic (Keep it clear and focused)
    for instance in instances:
        # Check if the instance is indeed a Leave object (extra safety)
        if not isinstance(instance, Leave):
            continue
            
        # Ensure 'duration' is not None before assignment
        duration_value = getattr(instance, 'duration', None)
        instance.number_of_days = duration_value