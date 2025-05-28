from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from payroll.utils import PayrollProcessor
from payroll.models import Payroll

#from payroll.tasks import Payer
from django.db import models


@receiver(pre_save, sender=Payroll)
def payroll_create(sender, instance, **kwargs):
    if 'errors' in instance._metadata: return
    instance._metadata['errors'] = []

@receiver(post_save, sender=Payroll)
def payroll_created(sender, instance, created, **kwargs):
    if not created: return
    
    # Duplicate payroll employees
    PayrollProcessor(instance).process()

    # start process of creating payroll employee
    # Payer().run(instance.id)
    # Payer().delay(instance.id)
    