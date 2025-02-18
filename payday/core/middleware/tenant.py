from django.http import HttpResponseRedirect
from django.core.cache import cache
from django.conf import settings

from core.utils import set_schema
from django.db import connection

import threading
import logging

logger = logging.getLogger(__name__)
thread = threading.local()

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.cache_timeout = 60 * 60  # Cache timeout in seconds (1 hour)

    def __call__(self, request):
        if getattr(settings, "DEBUG", True):
            response = self.get_response(request)
            return response
            
        schema = self.extract_schema_from_host(request.get_host())

        if not self.is_valid_schema(schema):
            logger.warning(f"Invalid schema: {schema}")
            return self.redirect_to_default()

        row = self.set_schema_from_cache_or_db(schema)
        if not row:
            return self.redirect_to_default()

        if not (is_active := row['is_active']):
            # send message to the user that the schema is not active
            logger.warning(f"Schema {schema} is not active")
            return self.redirect_to_default()

        set_schema(schema)
        request.tenant = row
        thread.schema = schema
        return self.get_response(request)

    def extract_schema_from_host(self, host):
        """
        Extract the schema (subdomain) from the request host.
        """
        return host.split(':')[0].split('.')[0]

    def is_valid_schema(self, schema):
        """
        Validate the schema (subdomain).
        """
        return schema and schema != "www"

    def set_schema_from_cache_or_db(self, schema):
        """
        Set the schema from cache or database.
        Returns True if the schema is valid and set, False otherwise.
        """
        key = f"tenant_{schema}"
        row = cache.get(key)
        if row:
            logger.debug(f"Using cached schema for {schema}")
            set_schema(schema)
            return row

        if row := self.set_schema_from_db(schema):
            cache.set(key, row, timeout=self.cache_timeout)
            logger.debug(f"Schema {schema} set and cached")
            return row

        return False

    def set_schema_from_db(self, schema):
        """
        Set the schema by querying the organization table in the public schema.
        Returns True if the schema exists, False otherwise.
        """
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM public.tenant WHERE schema = %s", [schema])
                if row := cursor.fetchone():
                    set_schema(schema)
                    col_names = [desc[0] for desc in cursor.description]
                    return dict(zip(col_names, row))
                logger.warning(f"Schema {schema} not found in organization table")
                return False
        except Exception as e:
            logger.error(f"Error querying organization table for schema {schema}: {e}")
            return False

    def redirect_to_default(self):
        """
        Redirect to the default URL with an optional error message.
        """
        redirect_url = getattr(settings, "DEFAULT_TENANT_REDIRECT_URL", "https://payday.cd")
        return HttpResponseRedirect(f"{redirect_url}?message=not-found")

    @staticmethod
    def get_schema():
        return getattr(thread, 'schema', None)

    @staticmethod 
    def get_tenant():
        schema = TenantMiddleware.get_schema()
        return cache.get(f"tenant_schema_{schema}", {})