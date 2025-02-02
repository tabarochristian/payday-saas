from django.db.models.signals import post_delete
from django.dispatch import receiver
from payroll.models import ItemPaid


@receiver(post_delete, sender=ItemPaid)
def item_paid_deleted(sender, instance, **kwargs):
    try:
        instance.employee.update()
        instance.employee.payroll.update()
    except Exception as ex:
        print(ex)