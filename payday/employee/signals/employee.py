from django.db.models.signals import post_save
from django.dispatch import receiver
from employee.models import Employee

from employee.tasks import send_employee_to_device
from core.middleware import TenantMiddleware


@receiver(post_save, sender=Employee)
def employee_created(sender, instance, created, **kwargs):
    if instance.create_user_on_save and instance.email:
        user = instance.create_user()
    
    schema = TenantMiddleware.get_schema()
    if instance.photo == None or schema == None: return
    send_employee_to_device.delay(schema, instance.pk)