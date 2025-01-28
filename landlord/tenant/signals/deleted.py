from django.db.models.signals import pre_delete
from tenant.tasks import delete_tenant_schema
from django.dispatch import receiver
from tenant.models import Tenant
from threading import Thread
import logging

# Set up logging
logger = logging.getLogger(__name__)

@receiver(pre_delete, sender=Tenant)
def deleted(sender, instance, **kwargs):
    try:
        # Create a new process
        thread = Thread(target=delete_tenant_schema, args=(instance.schema,))
        thread.daemon = True
        thread.start()

        # Log the start of the task
        logger.info(f"Started task for tenant {instance.id}")
    except Exception as e:
        # Log any errors
        logger.error(f"Error starting task for tenant {instance.id}: {e}")
