from django.db.models.signals import post_save
from django.dispatch import receiver
from easypay.models import *

#from payroll.tasks import Payer
from django.db import models

@receiver(post_save, sender=Mobile)
def mobile_payment_order_created(sender, instance, created, **kwargs):
    if not created: return
    