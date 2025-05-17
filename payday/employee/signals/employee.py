from django.db.models.signals import post_save
from django.contrib.auth import get_user_model
from django.dispatch import receiver
from employee.models import Employee

from core.middleware import TenantMiddleware
from core.models import Preference
from django.conf import settings
from employee.tasks import *
import threading

_thread_locals = threading.local()

@receiver(post_save, sender=Employee)
def employee_created(sender, instance, created, **kwargs):
    if instance.create_user_on_save and instance.email:
        user = instance.create_user()
    
    schema = TenantMiddleware.get_schema()
    if instance.photo == None or schema == None: return
    send_employee_to_device.delay(schema, instance.pk)