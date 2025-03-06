from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.contrib.auth import get_user_model
from django.conf import settings
from html2text import html2text
from core import utils

from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.forms import PasswordResetForm
from django.core.management import call_command
from django.db import connection
from core.models import Menu
from django.apps import apps

User = get_user_model()

class Command(BaseCommand):
    """
    A management command to run migrations for a specific tenant schema,
    create a master user, send welcome and password reset emails, 
    and optionally delete a tenant.
    """
    help = 'Run migrations for a specific tenant schema, create a master user, and optionally delete a tenant'
    black_list_schema = ['public', 'shared', 'www', 'minio', 'device', 'billing']

    def add_arguments(self, parser):
        parser.add_argument('schema', type=str, help='The schema name to run migrations on')
        parser.add_argument('email', type=str, help='The email to create master user')

    def handle(self, *args, **kwargs):
        """
        Main method to handle the command logic.
        """
        schema = kwargs['schema']
        email = kwargs['email']

        if schema in self.black_list_schema:
            self.stdout.write(self.style.ERROR('You cannot use the public schema.'))
            return

        # Ensure the schema exists and set it
        self.create_schema_if_not_exists(schema)
        utils.set_schema(schema)

        self.stdout.write(self.style.SUCCESS(f'Running migrations for schema "{schema}"...'))
        call_command('migrate')
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
            self.load_fixtures(schema, user)
            self.stdout.write(self.style.SUCCESS(f'Fixtures loaded for schema "{schema}".'))
            self.send_welcome_email(schema, user)
            self.stdout.write(self.style.SUCCESS(f'Welcome email sent to "{email}".'))
            self.send_password_reset_email(schema, user)
            self.stdout.write(self.style.SUCCESS(f'Password reset email sent to "{email}".'))
        else:
            self.stdout.write(self.style.SUCCESS(f'User "{email}" already exists.'))

    def create_schema_if_not_exists(self, schema_name):
        """
        Create a schema if it does not already exist.
        """
        with connection.cursor() as cursor:
            cursor.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s;", [schema_name])
            if cursor.fetchone():
                return
            cursor.execute(f'CREATE SCHEMA {schema_name};')

    def send_welcome_email(self, schema, user):
        """
        Send a welcome email to the user.
        """
        subject = "Welcome to Our Platform"
        html_message = render_to_string('email/welcome_email.html', {
            'user': user,
            'schema': schema,
            'site_name': 'Payday',
            'domain': 'payday.cd',
            'protocol': 'http',
            'support_email': settings.DEFAULT_FROM_EMAIL,
        })

        email = EmailMultiAlternatives(subject, html2text(html_message), settings.DEFAULT_FROM_EMAIL, [user.email])
        email.attach_alternative(html_message, 'text/html')
        email.send()

        self.stdout.write(self.style.SUCCESS(f'Welcome email sent to {user.email}.'))

    def send_password_reset_email(self, schema, user):
        """
        Send a password reset email to the user.
        """
        utils.set_schema(schema)
        form = PasswordResetForm({'email': user.email})
        if not form.is_valid():
            self.stdout.write(self.style.ERROR('Password reset form is invalid.'))
            return
        
        form.save(
            request=None,
            use_https=True,  # Set True if you're using HTTPS
            from_email=settings.DEFAULT_FROM_EMAIL,
            email_template_name='registration/password_reset_email.html',
            subject_template_name='registration/password_reset_subject.txt',
        )

    def load_fixtures(self, schema, user):
        """
        Load fixtures for a given schema.
        """
        exclude = ['document', 'child', 'education', 'advancesalarypayment', 'itempaid', 'paidemployee', 'specialemployeeitem']
        app_labels = ContentType.objects.exclude(
            app_label__in=['contenttypes', 'sessions', 'admin', 'auth', 'core']
        ).values_list('app_label', flat=True).distinct()
        
        for app_label in app_labels:
            obj, created = Menu.objects.get_or_create(name=app_label, created_by=user)
            if created:
                qs = ContentType.objects.filter(app_label=app_label)\
                    .exclude(model__in=exclude).only('id')
                obj.children.set(qs)
                self.stdout.write(self.style.SUCCESS(f'Created menu and sub-menu for {app_label}'))

        fixture_folder = 'fixtures'
        fixtures = ['core.json', 'employee.json', 'payroll.json'] 
        for fixture in fixtures:
            utils.set_schema(schema)
            call_command('loaddata', f'{fixture_folder}/{fixture}')
            self.stdout.write(self.style.SUCCESS(f'Loaded fixture "{fixture}".'))
