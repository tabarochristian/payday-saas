from django.db.models.signals import pre_save, post_save
from core.management.tenants import EmailService
from core.models import User, Preference, Group
from core.middleware import TenantMiddleware
from django.dispatch import receiver

@receiver(pre_save, sender=User)
def save(sender, instance, **kwargs):
    if instance.password: return
    if default_password := Preference.get('DEFAULT_USER_PASSWORD:STR'):
        instance.set_password(default_password)

@receiver(post_save, sender=User)
def saved(sender, instance, created, **kwargs):
    if not created: return
    group = Preference.get('DEFAULT_USER_ROLE:STR')
    group =  Group.objects.filter(name=group).first()
    if group: instance.groups.add(group)
    
    if schema:=TenantMiddleware.get_schema():
        EmailService().send_welcome_email(
            password = 'payday-pwd',
            tenant_name=schema,
            user = instance,
            schema = schema,
            plan = '-'
        )
    

