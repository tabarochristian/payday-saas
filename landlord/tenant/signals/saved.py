from tenant.tasks import create_tenant_schema, delete_tenant_schema
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from tenant.models import Tenant
import logging

# Set up logging
logger = logging.getLogger(__name__)

@receiver(post_save, sender=Tenant)
def saved(sender, instance, created, **kwargs):
    if not created:
        return
    
    try:
        create_tenant_schema.delay(instance.id)
        logger.info(f"Started task for tenant {instance.id}")
    except Exception as e:
        # Log any errors
        logger.error(f"Error starting task for tenant {instance.id}: {e}")
