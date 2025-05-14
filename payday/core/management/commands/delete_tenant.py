from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.conf import settings
import re
import logging
from typing import Optional
from tenants.schema import SchemaManager
from tenants.lago import LagoClient
from tenants.email import EmailService
from tenants.utils import generate_random_password

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """
    Django management command to delete a tenant.
    Removes Lago customer/subscriptions, superuser, and database schema.
    """
    help = 'Delete a tenant, including its Lago customer, subscriptions, superuser, and database schema'

    BLACKLISTED_SCHEMAS = {'public', 'shared', 'www', 'minio', 'device', 'billing', 'lago', 'redis', 'db'}

    def add_arguments(self, parser):
        parser.add_argument('schema', type=str, help='The schema name (subdomain) of the tenant to delete')

    def handle(self, *args, **kwargs) -> None:
        """
        Execute the tenant deletion process.
        """
        schema: str = kwargs['schema'].lower()

        # Initialize services
        schema_manager = SchemaManager()
        lago_client = LagoClient()

        # Validate input
        try:
            self._validate_input(schema, schema_manager, lago_client)
        except ValueError as e:
            self.stdout.write(self.style.ERROR(str(e)))
            return

        # Delete tenant
        try:
            self._delete_tenant(schema, schema_manager, lago_client)
            self.stdout.write(self.style.SUCCESS(f'Successfully deleted tenant "{schema}"'))
        except Exception as e:
            logger.error(f'Failed to delete tenant "{schema}": {str(e)}', exc_info=True)
            self.stdout.write(self.style.ERROR(f'Error deleting tenant: {str(e)}'))
            raise CommandError(str(e))

    def _validate_input(self, schema: str, schema_manager: 'SchemaManager', lago_client: 'LagoClient') -> None:
        """
        Validate the schema input.
        """
        if not schema or schema in self.BLACKLISTED_SCHEMAS:
            raise ValueError(f'Invalid or protected schema name: {schema}')
        if not re.match(r'^[a-z0-9-]{3,63}$', schema):
            raise ValueError(f'Invalid schema format: {schema}')
        if schema_manager.is_schema_unique(schema) and lago_client.is_customer_unique(schema):
            raise ValueError(f'Tenant "{schema}" does not exist')

    def _delete_tenant(
        self,
        schema: str,
        schema_manager: 'SchemaManager',
        lago_client: 'LagoClient'
    ) -> None:
        """
        Orchestrate tenant deletion with atomic transaction.
        """
        with transaction.atomic():
            lago_client.terminate_subscription(schema)
            self.stdout.write(self.style.SUCCESS(f'Terminated subscriptions for schema "{schema}"'))

            lago_client.delete_customer(schema)
            self.stdout.write(self.style.SUCCESS(f'Deleted Lago customer for schema "{schema}"'))

            schema_manager.delete_superuser(schema)
            self.stdout.write(self.style.SUCCESS(f'Deleted superuser for schema "{schema}"'))

            schema_manager.drop_schema(schema)
            self.stdout.write(self.style.SUCCESS(f'Dropped schema "{schema}"'))