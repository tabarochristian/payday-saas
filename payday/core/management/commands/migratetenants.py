from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import connection
from core import utils

class Command(BaseCommand):
    help = 'Run migrations for a specific tenant schema, create a master user, and optionally delete a tenant'
    black_list_schema = ['public', 'shared', 'www', 'minio', 'device', 'billing']

    def handle(self, *args, **kwargs):
        """
        Handle method to run migrations for all tenant schemas except those in the blacklist.
        """
        # Set the schema to public
        utils.set_schema("public")

        # Fetch all schemas from the tenant table in the public schema
        with connection.cursor() as cursor:
            cursor.execute("SELECT schema FROM public.tenant_tenant")
            schemas = cursor.fetchall()

        # create schema if not exists from schemas
        for schema in schemas:
            schema_name = schema[0]
            if schema_name in self.black_list_schema:
                continue

            with connection.cursor() as cursor:
                cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")

        # Iterate over each schema and run migrations
        for schema in schemas:
            schema_name = schema[0]
            if schema_name in self.black_list_schema:
                continue

            utils.set_schema(schema_name)
            call_command('migrate')

            self.stdout.write(self.style.SUCCESS(f"Successfully migrated schema {schema_name}"))

        self.stdout.write(self.style.SUCCESS("Successfully migrated all schemas"))
