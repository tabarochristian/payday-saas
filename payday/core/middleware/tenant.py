import logging
import threading
import requests

from django.core.cache import cache
from django.conf import settings
from django.http import HttpResponseRedirect

from core.utils import set_schema

logger = logging.getLogger(__name__)
_thread_locals = threading.local()

class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.api_key = getattr(settings, 'LAGO_API_KEY', None)
        self.api_url = getattr(settings, 'LAGO_API_URL', 'http://lago:3000')
        self.cache_timeout = getattr(settings, 'TENANT_CACHE_TIMEOUT', 3600)
        self.default_redirect = getattr(settings, 'DEFAULT_TENANT_REDIRECT_URL', 'http://payday.cd')
        
        if not self.api_key:
            logger.warning("LAGO_API_KEY not configured in settings.")

    def __call__(self, request):
        if getattr(settings, "DEBUG", False):
            return self.get_response(request)

        schema = self.extract_schema_from_host(request.get_host())
        if not self.is_valid_schema(schema):
            logger.warning(f"Invalid or missing schema from host: {request.get_host()}")
            return self.redirect_to_default("invalid-schema")

        tenant_info = self.get_or_fetch_tenant(schema)
        if not tenant_info or not tenant_info.get("is_active"):
            logger.warning(f"Tenant not found or inactive: {schema}")
            return self.redirect_to_default("inactive-or-missing")

        request.schema = schema
        _thread_locals.schema = schema
        request.tenant = tenant_info
        set_schema(schema)

        return self.get_response(request)

    def extract_schema_from_host(self, host):
        """Extract subdomain from the host, excluding port."""
        parts = host.split(":")[0].split(".")
        return parts[0] if len(parts) > 1 else None

    def is_valid_schema(self, schema):
        return schema and schema.lower() != 'www'

    def get_or_fetch_tenant(self, schema):
        """Returns tenant from cache or Lago, and stores it back if fetched."""
        cache_key = f"tenant_{schema.lower()}"
        tenant = cache.get(cache_key)
        if tenant:
            return tenant

        tenant = self.fetch_tenant_from_lago(schema)
        if tenant:
            cache.set(cache_key, tenant, timeout=self.cache_timeout)
        return tenant

    def fetch_tenant_from_lago(self, schema):
        """Fetch subscription info from Lago API and return enriched tenant data."""
        if not self.api_key:
            logger.error("Lago API key is missing.")
            return None

        try:
            response = requests.get(
                f"{self.api_url}/api/v1/subscriptions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                params={"external_customer_id": schema}
            )
            if response.status_code == 404:
                logger.info(f"No subscriptions found for schema: {schema}")
                return None

            response.raise_for_status()
            data = response.json()
            subscriptions = data.get("subscriptions", [])

            # Filter active-like subscriptions
            active_statuses = {"active", "trialing", "in_trial"}
            active_subs = [s for s in subscriptions if s.get("status") in active_statuses]

            if not active_subs:
                logger.info(f"No active subscriptions for schema: {schema}")
                return {"schema": schema, "is_active": False}

            first_sub = active_subs[0]
            return {
                "schema": schema,
                "external_id": schema,
                "is_active": True,
                "created_at": first_sub.get("created_at"),
                "lago_customer_id": first_sub.get("lago_customer_id"),
                "subscription_status": first_sub.get("status"),
            }

        except requests.RequestException as e:
            logger.exception(f"Failed to fetch Lago subscriptions for schema {schema}: {e}")
            return None

    def redirect_to_default(self, reason="not-found"):
        """Redirect to the default fallback URL with an error reason."""
        return HttpResponseRedirect(f"{self.default_redirect}?message={reason}")

    @staticmethod
    def get_schema():
        return getattr(_thread_locals, 'schema', None)

    @staticmethod
    def get_tenant():
        schema = TenantMiddleware.get_schema()
        if schema:
            return cache.get(f"tenant_{schema.lower()}", {})
        return {}
