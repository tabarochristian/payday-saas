from django.db.models.signals import post_save
from tenant.tasks import create_tenant_schema
from django.dispatch import receiver
from tenant.models import Tenant

@receiver(post_save, sender=Tenant)
def saved(sender, instance, created, **kwargs):
    if not created: return
    create_tenant_schema.delay(instance.serialized)
    