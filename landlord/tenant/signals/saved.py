from tenant.tasks import create_tenant_schema, delete_tenant_schema
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from tenant.models import Tenant
import logging
import multiprocessing

# Set up logging
logger = logging.getLogger(__name__)

@receiver(post_save, sender=Tenant)
def saved(sender, instance, created, **kwargs):
    if not created:
        return
    
    try:
        # Create a new process
        process = multiprocessing.Process(target=create_tenant_schema, args=(instance.id,))
        
        # Start the process
        process.start()
        
        # Don't wait for the process to finish
        logger.info(f"Started task for tenant {instance.id}")
    except Exception as e:
        # Log any errors
        logger.error(f"Error starting task for tenant {instance.id}: {e}")
