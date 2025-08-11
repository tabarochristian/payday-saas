from django.contrib.auth.forms import PasswordResetForm
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from django.conf import settings
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class EmailService:
    """
    Handles sending welcome and password reset emails for tenants.
    """

    def send_welcome_email(
        self,
        schema: str,
        user,
        password: str,
        tenant_name: Optional[str],
        plan: str
    ) -> None:
        """
        Send a welcome email to the user with their temporary password.
        """
        try:
            subject = f"Bienvenue sur Payday !"
            context = {
                'user': user,
                'schema': schema,
                'password': password,
                'tenant_name': tenant_name or schema,
                'plan': plan,
                'protocol': 'http',
                'domain': getattr(settings, 'DEFAULT_TENANT_REDIRECT_URL', 'http://payday.cd').replace('http://', ''),
                'support_email': getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@localhost')
            }
            html_message = render_to_string('email/welcome_email.html', context)
            plain_message = render_to_string('email/welcome_email.txt', context)
            email = EmailMultiAlternatives(
                subject=subject,
                body=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email.strip()]
            )
            email.attach_alternative(html_message, 'text/html')
            email.send()
            logger.info(f'Sent welcome email to {user.email}')
            print("Ok", user.email)
        except Exception as ex:
            print("Not Ok", user.email, str(ex))

    def send_password_reset_email(self, schema: str, user: 'User') -> None:
        """
        Send a password reset email to the user.
        """
        from core.utils import set_schema
        set_schema(schema)
        form = PasswordResetForm({'email': user.email})
        if not form.is_valid():
            raise ValueError('Invalid email for password reset')
        form.save(
            domain_override=getattr(settings, 'DEFAULT_TENANT_REDIRECT_URL', 'http://payday.cd').replace('http://', ''),
            use_https=False,
            from_email=settings.DEFAULT_FROM_EMAIL,
            email_template_name='registration/password_reset_email.html',
            subject_template_name='registration/password_reset_subject.txt',
            html_email_template_name='registration/password_reset_email.html'
        )
        logger.info(f'Sent password reset email to {user.email}')