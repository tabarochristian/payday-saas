from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver

from payroll.utils import PayrollProcessor
from payroll.models import Payroll
from django.apps import apps
import threading

from core.middleware import TenantMiddleware


@receiver(pre_save, sender=Payroll)
def payroll_create(sender, instance, **kwargs):
    if 'errors' in instance._metadata: return
    instance._metadata['errors'] = []

@receiver(post_save, sender=Payroll)
def payroll_created(sender, instance, created, **kwargs):
    if not created: return
    schema = TenantMiddleware.get_schema() or "public"
    threading.Thread(target=PayrollProcessor(instance, schema).process, daemon=True).start()

@receiver(post_delete, sender=Payroll)
def payroll_deleted(sender, instance, **kwargs):
    model = apps.get_model('easypay', model_name='mobile')
    model.objects.filter(payroll__pk=instance.pk).delete()
    
    model = apps.get_model('payroll', model_name='paidemployee')
    model.objects.filter(payroll__pk=instance.pk).delete()