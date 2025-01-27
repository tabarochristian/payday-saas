from django.db.models.signals import pre_delete
from tenant.tasks import delete_tenant_schema

from django.dispatch import receiver
from joblib import Parallel, delayed
from tenant.models import Tenant
import logging

@receiver(pre_delete, sender=Tenant)
def deleted(sender, instance, **kwargs):
    try:
        job = Parallel(n_jobs=1)
        delayer = delayed(delete_tenant_schema)
        
        # Log success
        job([delayer(instance.schema)])
        logger.info(f"Task for tenant {instance.id} started successfully.")
    except Exception as e:
        # Log any errors
        logger.error(f"Error starting task for tenant {instance.id}: {e}")