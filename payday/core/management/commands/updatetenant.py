from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.db import connection
import json

class Command(BaseCommand):
    help = 'Update the tenant table in the public schema with key-value arguments and update the cache'

    def add_arguments(self, parser):
        parser.add_argument('schema', type=str, help='The schema name to update')
        parser.add_argument('--fields', nargs='+', help='Key-value pairs to update the tenant table')

    def handle(self, *args, **kwargs):
        schema = kwargs['schema']
        fields = kwargs['fields']

        #if not fields:
        #    self.stdout.write(self.style.ERROR('No fields provided for update.'))
        #    return

        # Ensure the tenant exists
        tenant_data = self.get_tenant(schema)
        if not tenant_data:
            self.stdout.write(self.style.ERROR(f'Tenant with schema "{schema}" does not exist.'))
            return

        # Update the cache key with the updated tenant row dictionary
        cache_key = f'tenant_{schema}'
        cache.set(cache_key, tenant_data)

        self.stdout.write(self.style.SUCCESS(f'Cache key "{cache_key}" has been updated with the tenant data.'))
        self.stdout.write(self.style.SUCCESS(f'Tenant data: {tenant_data}'))

    def get_tenant(self, schema):
        """
        Retrieve the tenant row as a dictionary using raw SQL.
        """
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM public.tenant_tenant WHERE schema_name = %s;", [schema])
            row = cursor.fetchone()
            if not row: return None
            row = dict(zip([col[0] for col in cursor.description], row))
            row['plan'] = json.loads(row['plan'])
            return row
        return None