from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.contrib.auth import get_user_model
from django.conf import settings
from core import utils

User = get_user_model()

class Command(BaseCommand):
    help = 'Run migrations for a specific tenant schema and create a master user'

    def add_arguments(self, parser):
        parser.add_argument('schema', type=str, help='The schema name to run migrations on')
        parser.add_argument('email', type=str, help='The email to create master user')

    def handle(self, *args, **kwargs):
        schema = kwargs['schema']
        email = kwargs['email']

        # Ensure the schema exists and set it
        utils.create_schema_if_not_exists(schema)
        utils.set_schema(schema)

        self.stdout.write(self.style.SUCCESS(f'Running migrations for schema "{schema}"...'))
        from django.core.management import call_command
        call_command('migrate')

        # Prepare and add the default menu (if needed)
        self.stdout.write(self.style.SUCCESS(f'Successfully ran migrations for schema "{schema}".'))

        # Create or get the user
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'is_superuser': True,
                'is_active': True,
                'is_staff': True
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f'User "{email}" created.'))
            self.send_welcome_email(user, schema)

            # self.send_password_reset_email(user, schema)

    def send_welcome_email(self, user, schema):
        """
        Send a welcome email to the user.
        """
        subject = "Welcome to Our Platform"
        message = render_to_string('email/welcome_email.html', {
            'user': user,
            'schema': schema,
            'site_name': 'Payday',
            'domain': 'payday.cd',
            'protocol': 'http',
            'support_email': settings.DEFAULT_FROM_EMAIL,
        })

        # Use the User model's email_user method to send the email
        user.email_user(subject, message)
        self.stdout.write(self.style.SUCCESS(f'Welcome email sent to {user.email}.'))
