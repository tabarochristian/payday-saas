import logging
from django.dispatch import receiver
from django.db.models.signals import pre_save, post_save
from core.models import User, Preference, Group

from core.management.tenants import EmailService
from core.middleware import TenantMiddleware


logger = logging.getLogger(__name__)

@receiver(pre_save, sender=User)
def set_default_user_password(sender, instance, **kwargs):
    if instance.password and instance.has_usable_password():
        return
    if default_password := Preference.get('DEFAULT_USER_PASSWORD:STR'):
        instance.set_password(default_password)
        logger.info(f"Default password set for user: {instance.email}")

@receiver(post_save, sender=User)
def assign_group_and_send_email(sender, instance, created, **kwargs):
    if not created:
        return

    schema = TenantMiddleware.get_schema()
    group_name = Preference.get('DEFAULT_USER_ROLE:STR')
    groups = Group.objects.filter(name=group_name)

    if groups:
        instance.groups.set(groups)
        group = groups.values_list('name', flat=True)
        group_names = ', '.join(instance.groups.all().values_list('name', flat=True))
        logger.info(f"User '{instance.email}' assigned to group '{group.name}' in schema '{schema}'. Full group list: [{group_names}]")

    try:
        EmailService().send_welcome_email(
            password='payday-pwd',
            tenant_name=schema,
            user=instance,
            schema=schema,
            plan='-'
        )
        logger.info(f"Welcome email sent to user '{instance.email}' in schema '{schema}'")
    except Exception as e:
        logger.error(f"Error sending welcome email to '{instance.email}': {e}")
