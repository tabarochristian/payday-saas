from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.contrib.auth import get_user_model

from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.db import connection

from html2text import html2text
from core import utils


User = get_user_model()

class Command(BaseCommand):
    help = 'Run migrations for a specific tenant schema, create a master user, and optionally delete a tenant'

    def add_arguments(self, parser):
        parser.add_argument('schema', type=str, help='The schema name to run migrations on')
        parser.add_argument('email', type=str, help='The email to create master user')
        parser.add_argument('--delete', action='store_true', help='Delete the tenant')

    def handle(self, *args, **kwargs):
        delete = kwargs.get('delete', False)
        email = kwargs.get('email', None)
        schema = kwargs['schema']

        if schema == 'public':
            self.stdout.write(self.style.ERROR('You cannot use the public schema.'))
            return

        if delete:
            utils.set_schema("public")
            with connection.cursor() as cursor:
                cursor.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
            self.stdout.write(self.style.SUCCESS(f'Tenant "{schema}" deleted successfully'))
            return

        # Ensure the schema exists and set it
        utils.create_schema_if_not_exists(schema)
        utils.set_schema(schema)

        self.stdout.write(self.style.SUCCESS(f'Running migrations for schema "{schema}"...'))
        from django.core.management import call_command
        call_command('migrate')

        # Prepare and add the default menu (if needed)
        self.stdout.write(self.style.SUCCESS(f'Successfully ran migrations for schema "{schema}".'))

        # Create or get the user
        if email is None: return
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'is_superuser': True,
                'is_active': True,
                'is_staff': True
            }
        )

        if not created: return
        
        from django.contrib.contenttypes.models import ContentType
        content_types = ContentType.objects.filter(app_label__in=['employee', 'payroll'])
        excluded_models = ['children','itempaid','paidemployee','advancesalary','specialemployeeitem']
        
        for content_type in content_types:
            self.create_or_get_menu(user, content_type.app_label, excluded_models=excluded_models)

        self.stdout.write(self.style.SUCCESS(f'User "{email}" created.'))
        self.send_welcome_email(user, schema)

    def send_welcome_email(self, user, schema):
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

        # Use the User model's email_user method to send the email
        email = EmailMultiAlternatives(subject, html2text(html_message), settings.DEFAULT_FROM_EMAIL, [user.email])
        email.attach_alternative(html_message, 'text/html')
        email.send()

        self.stdout.write(self.style.SUCCESS(f'Welcome email sent to {user.email}.'))

    def create_or_get_menu(self, user, name, excluded_models=[]):
        from core.models import Menu
        obj, created = Menu.objects.get_or_create(**{
            'name': name,
            'created_by': user
        })
        if not created: return obj
        qs = ContentType.objects\
            .filter(app_label=app_label)\
                .exclude(model__in=excluded_models)
        obj.children.set(qs)
        self.stdout.write(self.style.SUCCESS(f'Menu "{obj.name}" created.'))

