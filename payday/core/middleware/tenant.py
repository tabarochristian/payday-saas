from django.http import HttpResponseRedirect
from django.core.cache import cache
from django.conf import settings
import requests
import logging
import threading

logger = logging.getLogger(__name__)
thread = threading.local()

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.cache_timeout = getattr(settings, 'TENANT_CACHE_TIMEOUT', 60 * 60)
        self.lago_api_url = getattr(settings, 'LAGO_API_URL', 'http://lago:3000')
        self.lago_api_key = getattr(settings, 'LAGO_API_KEY', "23e0a6aa-a0a7-4dc9-bec6-e225bf65ec05")

    def __call__(self, request):
        if getattr(settings, "DEBUG", True):
            response = self.get_response(request)
            return response
        
        host = request.get_host()
        schema = self.extract_schema_from_host(host)

        if not self.is_valid_schema(schema):
            logger.warning(f"Invalid schema: {schema}")
            return self.redirect_to_default()

        row = self.set_schema_from_cache_or_lago(schema)
        if not row:
            return self.redirect_to_default()

        if not (is_active := row.get('is_active', False)):
            logger.warning(f"Schema {schema} is not active")
            return self.redirect_to_default()

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

    def set_schema_from_cache_or_lago(self, schema):
        """
        Set the schema from cache or Lago API.
        Returns customer data if valid and set, False otherwise.
        """
        key = f"tenant_{schema}"
        row = cache.get(key.lower())
        if row:
            logger.debug(f"Using cached schema for {schema}")
            return row

        if row := self.set_schema_from_lago(schema):
            cache.set(key, row, timeout=self.cache_timeout)
            logger.debug(f"Schema {schema} set and cached")
            return row

        return False

    def set_schema_from_lago(self, schema):
        """
        Check customer status via Lago API.
        Returns customer data with is_active status if the customer exists, False otherwise.
        """
        if not self.lago_api_key:
            logger.error("Lago API key not configured")
            return False

        try:
            # Fetch customer from Lago
            headers = {"Authorization": f"Bearer {self.lago_api_key}"}
            response = requests.get(f"{self.lago_api_url}/api/v1/customers/{schema}", headers=headers)
            
            if response.status_code == 404:
                logger.warning(f"Customer {schema} not found in Lago")
                return False
            
            response.raise_for_status()
            customer_data = response.json().get('customer', {})

            # Check subscriptions for active status
            is_active = any(
                sub.get('status') == 'active' and not sub.get('terminated_at')
                for sub in customer_data.get('subscriptions', [])
            )

            # Prepare row data
            row = {
                'external_id': customer_data.get('external_id'),
                'is_active': is_active,
                'lago_id': customer_data.get('lago_id'),
                'name': customer_data.get('name'),
                'created_at': customer_data.get('created_at'),
                'schema': schema
            }
            return row

        except requests.RequestException as e:
            logger.error(f"Error querying Lago API for schema {schema}: {e}")
            return False

    def redirect_to_default(self):
        """
        Redirect to the default URL with an optional error message.
        """
        redirect_url = getattr(settings, "DEFAULT_TENANT_REDIRECT_URL", "http://payday.cd")
        return HttpResponseRedirect(f"{redirect_url}?message=not-found")

    @staticmethod
    def get_schema():
        return getattr(thread, 'schema', None)

    @staticmethod 
    def get_tenant():
        schema = TenantMiddleware.get_schema()
        return cache.get(f"tenant_{schema}", {})