from django.db.models.signals import post_save
from django.contrib.auth import get_user_model
from django.dispatch import receiver
from employee.models import Employee

from core.middleware import TenantMiddleware
from employee.tasks import setuserinfo
from core.models import Preference
from django.conf import settings

@receiver(post_save, sender=Employee)
def employee_created(sender, instance, created, **kwargs):
    if Preference.get('CREATE_USER_ON_EMPLOYEE', True) and instance.email:
        user = instance.create_user()