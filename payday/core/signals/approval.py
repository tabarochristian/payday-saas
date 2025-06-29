from django.utils.translation import gettext_lazy as _
from django.db.models.signals import post_save
from core.middleware import TenantMiddleware
from django.dispatch import receiver
from django.urls import reverse

from core.models import Approval

@receiver(post_save, sender=Approval)
def handle_approval(sender, instance, created, **kwargs):
    """
    On creation of an Approval instance, notifies the assigned approver via email.
    """
    if not created:
        return

    user = instance.user
    if not user.email:
        return

    subject = _("Demande d'approbation en attente")

    schema = TenantMiddleware.get_schema()
    url = f"http://{schema}.payday.cd" if schema else "http://payday.cd"
    approval_url = url + reverse('approval:detail', args=[instance.pk])
    message = _(
        "Bonjour {name},\n\n"
        "Une nouvelle demande nécessite votre approbation.\n"
        "Veuillez vous connecter à la plateforme pour approuver ou rejeter cette demande :\n\n"
        "{url}\n\n"
        "Merci."
    ).format(name=user.email, url=approval_url)
    user.email_user(subject=subject, message=message)
