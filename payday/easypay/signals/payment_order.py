from django.db.models.signals import post_save
from django.dispatch import receiver
from easypay.models import *

from django.db.models.functions import Concat
from payroll.models import PaidEmployee
from django.db import models


@receiver(post_save, sender=Mobile)
def mobile_payment_order_created(sender, instance, created, **kwargs):
    if not created: return

    annotate_fields = {
    }

    qs = PaidEmployee.objects.filter(
        payment_method = 'MOBILE MONEY',
        payroll = instance.payroll,
    ).exclude(
        mobile_number__isnull=True
    ).annotate(
        full_name=Concat('last_name', models.Value(' '), 'middle_name'),
    ).values(
        'mobile_number',
        'full_name'
        'net'
    )
    