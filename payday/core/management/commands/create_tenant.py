from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.conf import settings
from typing import Optional
import re
import logging

from core.management.tenants.utils import generate_random_password
from core.management.tenants.schema import SchemaManager
from core.management.tenants.email import EmailService
from core.management.tenants.lago import LagoClient

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """
    Django management command to create a new tenant.
    Orchestrates schema creation, Lago customer/subscription, superuser, and emails.
    """
    help = 'Create a new tenant with a Lago customer, assign an active plan, create a schema, superuser, and send emails'

    BLACKLISTED_SCHEMAS = {'public', 'shared', 'www', 'minio', 'device', 'billing', 'lago', 'redis', 'db'}

    def add_arguments(self, parser):
        parser.add_argument('schema', type=str, help='The schema name (subdomain) for the tenant')
        parser.add_argument('email', type=str, help='The email address for the tenant superuser')
        parser.add_argument('plan', type=str, help='The active Lago plan code to assign to the tenant')
        parser.add_argument('--coupon', type=str, help='The coupon\'s name', default=None)
        parser.add_argument('--name', type=str, help='The customer or organization name', default=None)

    def handle(self, *args, **kwargs) -> None:
        """
        Execute the tenant creation process.
        """
        schema: str = kwargs['schema'].lower()
        email: str = kwargs['email']
        plan: str = kwargs['plan']
        
        coupon: Optional[str] = kwargs.get('coupon')
        name: Optional[str] = kwargs.get('name') or schema

        schema_manager = SchemaManager()
        email_service = EmailService()
        lago_client = LagoClient()

        try:
            self._validate_inputs(schema, email, plan, lago_client, coupon)
        except ValueError as e:
            self.stdout.write(self.style.ERROR(str(e)))
            return

        try:
            password = generate_random_password()
            self._create_tenant(
                schema, email, plan, name, password,
                schema_manager, lago_client, email_service, coupon
            )
            self.stdout.write(self.style.SUCCESS(f'Successfully created tenant "{schema}" for "{email}"'))
        except Exception as e:
            logger.error(f'Failed to create tenant "{schema}": {str(e)}', exc_info=True)
            self.stdout.write(self.style.ERROR(f'Error creating tenant: {str(e)}'))
            lago_client.cleanup(schema)
            raise CommandError(str(e))

    def _validate_inputs(self, schema: str, email: str, plan: str, lago_client: LagoClient, coupon: Optional[str]) -> None:
        """
        Validate schema, email, plan, and coupon.
        """
        if not self._is_valid_schema(schema, lago_client):
            raise ValueError(f'Invalid schema name or schema already exists: {schema}')
        if not self._is_valid_email(email):
            raise ValueError(f'Invalid email address: {email}')
        if not lago_client.is_valid_plan(plan):
            raise ValueError(f'Invalid or inactive plan code: {plan}')
        if coupon and not lago_client.is_valid_coupon(coupon):
            raise ValueError(f'Invalid or inactive coupon code: {coupon}')

    def _is_valid_schema(self, schema: str, lago_client: LagoClient) -> bool:
        """
        Validate schema name and check uniqueness in database and Lago.
        """
        if not schema or schema in self.BLACKLISTED_SCHEMAS:
            return False
        if not re.match(r'^[a-z0-9-]{3,63}$', schema):
            return False
        return SchemaManager().is_schema_unique(schema) and lago_client.is_customer_unique(schema)

    def _is_valid_email(self, email: str) -> bool:
        """
        Validate email format.
        """
        return bool(re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email))

    def _create_tenant(
        self,
        schema: str,
        email: str,
        plan: str,
        name: str,
        password: str,
        schema_manager: SchemaManager,
        lago_client: LagoClient,
        email_service: EmailService,
        coupon: Optional[str]
    ) -> None:
        """
        Orchestrate tenant creation with atomic transaction.
        """
        with transaction.atomic():
            lago_client.create_customer(schema, email, name)
            self.stdout.write(self.style.SUCCESS(f'Created Lago customer for schema "{schema}"'))

            if coupon:
                lago_client.assign_coupon(schema, email, name, coupon)
                self.stdout.write(self.style.SUCCESS(f'Assigned coupon "{coupon}" to schema "{schema}"'))

            lago_client.assign_plan(schema, plan)
            self.stdout.write(self.style.SUCCESS(f'Assigned plan "{plan}" to schema "{schema}"'))

            schema_manager.create_schema(schema)
            self.stdout.write(self.style.SUCCESS(f'Created schema "{schema}"'))

            schema_manager.apply_migrations(schema)
            self.stdout.write(self.style.SUCCESS(f'Applied migrations for schema "{schema}"'))

            user = schema_manager.create_superuser(schema, email, password)
            self.stdout.write(self.style.SUCCESS(f'Created superuser "{email}" for schema "{schema}"'))

            email_service.send_welcome_email(schema, user, password, name, plan)
            self.stdout.write(self.style.SUCCESS(f'Sent welcome and password reset emails to "{email}"'))
