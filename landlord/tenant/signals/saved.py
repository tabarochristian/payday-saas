from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from tenant.models import Tenant
from threading import Thread
from tenant.tasks import *
import logging

# Set up logging
logger = logging.getLogger(__name__)

@receiver(post_save, sender=Tenant)
def saved(sender, instance, created, **kwargs):
    if not created:
        #thread = Thread(target=update_tenant_schema, args=(instance.id,))
        #logger.info(f"Started task for tenant update {instance.id}")
        #thread.daemon = True
        #thread.start()
        update_tenant_schema(instance.id)
        return
    
    # if tenant is created
    #thread = Thread(target=create_tenant_schema, args=(instance.id,))
    #logger.info(f"Started task for tenant {instance.id}")
    #thread.daemon = True
    #thread.start()
    create_tenant_schema(instance.id)
