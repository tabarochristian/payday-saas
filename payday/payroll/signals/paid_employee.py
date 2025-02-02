from django.db.models.signals import post_delete
from payroll.models import PaidEmployee
from django.dispatch import receiver

@receiver(post_delete, sender=PaidEmployee)
def item_paid_deleted(sender, instance, **kwargs):
    try:
        instance.payroll.update()
    except Exception as ex:
        print(ex)