from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connection
from core import utils

class Command(BaseCommand):
    help = 'Run migrations for a specific tenant schema, create a master user, and optionally delete a tenant'

    def add_arguments(self, parser):
        parser.add_argument('schema', type=str, help='The schema name to run migrations on')

    def handle(self, *args, **kwargs):
        """
        Handle method to run migrations for a specific tenant schema.
        """
        schema = kwargs['schema']

        try:
            utils.set_schema(schema)
            call_command('migrate')
            self.stdout.write(self.style.SUCCESS(f"Successfully migrated schema {schema}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to migrate schema {schema}: {e}"))
