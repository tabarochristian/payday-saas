from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.contrib.auth.forms import PasswordResetForm
from django.conf import settings
from smtplib import SMTPException
from tenacity import retry, stop_after_attempt, wait_none, retry_if_exception_type, before_sleep_log
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class EmailService:
    """
    Handles sending welcome and password reset emails for tenants.
    """

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_none(),
        retry=retry_if_exception_type((SMTPException, ConnectionError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def send_welcome_email(
        self,
        schema: str,
        user: 'User',
        password: str,
        tenant_name: Optional[str],
        plan: str
    ) -> None:
        """
        Send a welcome email to the user with their temporary password.
        """
        subject = f"Bienvenue sur Payday !"
        context = {
            'user': user,
            'schema': schema,
            'password': password,
            'tenant_name': tenant_name or schema.title(),
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
            to=[user.email]
        )
        email.attach_alternative(html_message, 'text/html')
        email.send()
        logger.info(f'Sent welcome email to {user.email}')

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_none(),  # No waiting between retries
        retry=retry_if_exception_type((Exception,)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
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