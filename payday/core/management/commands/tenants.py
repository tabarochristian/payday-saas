from django.core.management.base import BaseCommand
from django.db import connection
from core import utils

black_list_schema = ['public', 'shared', 'www', 'minio', 'device', 'billing']

class Command(BaseCommand):
    help = 'Run migrations for a specific tenant schema, create a master user, and optionally delete a tenant'

    def handle(self, *args, **kwargs):
        utils.set_schema("public")

        # using connection fetch all schema in the table tenants in the db
        with connection.cursor() as cursor:
            cursor.execute("SELECT schema FROM information_schema.schemata")
            schemas = cursor.fetchall()

        from django.core.management import call_command
        
        for schema in schemas:
            schema_name = schema[0]
            if schema_name in black_list_schema: continue

            utils.set_schema(schema_name)
            call_command('migrate')

            self.stdout.write(self.style.SUCCESS(f"Successfully migrated schema {schema_name}"))
        
        self.stdout.write(self.style.SUCCESS("Successfully migrated all schemas"))