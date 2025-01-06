from django.db.models.signals import pre_save, post_save
from core.models import User, Preference, Group
from django.dispatch import receiver


@receiver(pre_save, sender=User)
def save(sender, instance, **kwargs):
    if instance.password: return
    if default_password := Preference.get('DEFAULT_USER_PASSWORD:STR'):
        instance.set_password(default_password)
        instance.save()

@receiver(post_save, sender=User)
def saved(sender, instance, created, **kwargs):
    if not created: return
    group = Preference.get('DEFAULT_USER_ROLE:STR')
    if groups := Group.objects.filter(name=group):
        instance.groups.add(*groups)
