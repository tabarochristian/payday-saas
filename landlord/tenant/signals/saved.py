from tenant.tasks import create_tenant_schema, delete_tenant_schema
from django.db.models.signals import post_save, post_delete

from django.dispatch import receiver
from joblib import Parallel, delayed
from tenant.models import Tenant
import logging

# Set up logging
logger = logging.getLogger(__name__)

@receiver(post_save, sender=Tenant)
def saved(sender, instance, created, **kwargs):
    if not created:
        return
    
    try:
        job = Parallel(n_jobs=1)
        delayer = delayed(create_tenant_schema)
        
        # Log success
        job([delayer(instance.id)])
        logger.info(f"Task for tenant {instance.id} started successfully.")
    except Exception as e:
        # Log any errors
        logger.error(f"Error starting task for tenant {instance.id}: {e}")


@receiver(post_delete, sender=Tenant)
def deleted(sender, instance, **kwargs):
    try:
        job = Parallel(n_jobs=1)
        delayer = delayed(delete_tenant_schema)
        
        # Log success
        job([delayer(instance.id)])
        logger.info(f"Task for tenant {instance.id} started successfully.")
    except Exception as e:
        # Log any errors
        logger.error(f"Error starting task for tenant {instance.id}: {e}")