from django.db.models.signals import post_save
from django.contrib.auth import get_user_model
from django.dispatch import receiver
from employee.models import Employee

from core.middleware import TenantMiddleware
from employee.tasks import setuserinfo
from core.models import Preference
from django.conf import settings
from employee.tasks import *
import threading

_thread_locals = threading.local()

@receiver(post_save, sender=Employee)
def employee_created(sender, instance, created, **kwargs):
    if Preference.get('CREATE_USER_ON_EMPLOYEE', True) and instance.email:
        user = instance.create_user()
    
    schema = getattr(_thread_locals, "schema", None)
    if instance.photo == None or schema == None: return
    send_employee_to_device.delay(schema, instance.pk)