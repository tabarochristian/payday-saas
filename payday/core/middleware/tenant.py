from django.http import HttpResponseRedirect
from django.core.cache import cache
from core.utils import set_schema
from django.conf import settings

import threading
import requests
import logging

logger = logging.getLogger(__name__)
thread = threading.local()

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.lago_api_key = getattr(settings, 'LAGO_API_KEY', '23e0a6aa-a0a7-4dc9-bec6-e225bf65ec05')
        self.lago_api_url = getattr(settings, 'LAGO_API_URL', 'http://lago:3000')
        self.cache_timeout = getattr(settings, 'TENANT_CACHE_TIMEOUT', 60 * 60)

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

        request.schema = schema
        thread.schema = schema
        request.tenant = row
    
        set_schema(schema)
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
        key = f"tenant_{schema.lower()}"
        row = cache.get(key)
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
        Check customer status via Lago API subscriptions endpoint.
        Returns customer data with is_active status if the customer exists, False otherwise.
        """
        if not self.lago_api_key:
            logger.error("Lago API key not configured")
            return False

        try:
            # Fetch active subscriptions from Lago
            headers = {"Authorization": f"Bearer {self.lago_api_key}"}
            response = requests.get(
                f"{self.lago_api_url}/api/v1/subscriptions",
                params={"external_customer_id": schema, "status[]": "active"},
                headers=headers
            )
            
            if response.status_code == 404:
                logger.warning(f"Customer {schema} not found in Lago")
                return False
            
            response.raise_for_status()
            subscription_data = response.json()
            subscriptions = subscription_data.get('subscriptions', [])

            # Determine if customer is active based on subscriptions
            is_active = len(subscriptions) > 0

            # Prepare row data
            row = {
                'external_id': schema,
                'is_active': is_active,
                'lago_id': subscriptions[0].get('lago_customer_id') if subscriptions else None,
                'name': None,  # Name not available in subscriptions endpoint
                'created_at': subscriptions[0].get('created_at') if subscriptions else None,
                'schema': schema
            }

            # Optional: Check wallets if no active subscriptions (uncomment if needed)
            """
            if not is_active:
                wallet_response = requests.get(
                    f"{self.lago_api_url}/api/v1/wallets",
                    params={"lago_customer_id": row['lago_id']},
                    headers=headers
                )
                wallet_response.raise_for_status()
                wallets = wallet_response.json().get('wallets', [])
                is_active = any(
                    wallet.get('status') == 'active' and not wallet.get('terminated_at')
                    for wallet in wallets
                )
                row['is_active'] = is_active
            """

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
        return cache.get(f"tenant_{schema.lower()}", {})