from django.http import HttpResponseRedirect
from django.core.cache import cache
from django.conf import settings
from django.db import connection

from core.utils import set_schema
import logging

logger = logging.getLogger(__name__)

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

        if not self.set_schema_from_cache_or_db(schema):
            return self.redirect_to_default()

        set_schema(schema)
        request.tenant = schema
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
        cached_schema = cache.get(f"tenant_schema_{schema}")
        if cached_schema:
            logger.debug(f"Using cached schema for {schema}")
            set_schema(cached_schema)
            return True

        if self.set_schema_from_db(schema):
            cache.set(f"tenant_schema_{schema}", schema, timeout=self.cache_timeout)
            logger.debug(f"Schema {schema} set and cached")
            return True

        return False

    def set_schema_from_db(self, schema):
        """
        Set the schema by querying the organization table in the public schema.
        Returns True if the schema exists, False otherwise.
        """
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT id FROM public.tenant WHERE schema = %s", [schema])
                if cursor.fetchone():
                    set_schema(schema)
                    return True
                else:
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