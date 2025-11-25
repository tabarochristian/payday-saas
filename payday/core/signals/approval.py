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

    detail = getattr(instance.content_object, "name", "N/A")
    subject = _(f"Demande d'approbation : {detail}")
    schema = TenantMiddleware.get_schema()

    url = f"http://{schema}.payday.cd" if schema else "http://payday.cd"
    approval_url = url + reverse('core:change', kwargs={
        'app': instance.content_type.app_label,
        'model': instance.content_type.model,
        'pk': instance.object_id
    })

    message = _(
        "{name},\n\n"
        "Une nouvelle demande nécessite votre approbation.\n"
        "Veuillez vous connecter à la plateforme pour approuver ou rejeter cette demande :\n\n"
        "{url}\n\n"
        "Detail sur la demande: {detail}\n\n"
        "Merci."
    ).format(
        name=user.email, 
        url=approval_url, 
        detail=detail
    )
    user.email_user(subject=subject, message=message)
