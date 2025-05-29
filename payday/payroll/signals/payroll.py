from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver

from payroll.utils import PayrollProcessor
from payroll.models import Payroll
from django.db import models
from django.apps import apps


@receiver(pre_save, sender=Payroll)
def payroll_create(sender, instance, **kwargs):
    if 'errors' in instance._metadata: return
    instance._metadata['errors'] = []

@receiver(post_save, sender=Payroll)
def payroll_created(sender, instance, created, **kwargs):
    if not created: return
    PayrollProcessor(instance).process()
    

@receiver(post_delete, sender=Payroll)
def payroll_deleted(sender, instance, **kwargs):
    model = apps.get_model('easypay', model_name='mobile')
    model.objects.filter(payroll__pk=instance.pk).delete()
    
    model = apps.get_model('payroll', model_name='paidemployee')
    model.objects.filter(payroll__pk=instance.pk).delete()