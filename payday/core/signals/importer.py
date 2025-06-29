from django.db.models.signals import post_save
from core.middleware import TenantMiddleware
from django.dispatch import receiver
from django.conf import settings

from core.models import Importer
from core import tasks

@receiver(post_save, sender=Importer)
def handle_importer_created(sender, instance, created, **kwargs):
    """
    Handles the Importer post-save signal. Triggers the importer task on creation.
    """
    if not created:
        return

    task = tasks.importer if settings.DEBUG else tasks.importer.delay
    task(instance.pk, schema=TenantMiddleware.get_schema())
