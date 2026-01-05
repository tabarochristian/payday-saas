from typing import Callable, Optional
import threading
import logging

import requests
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.utils.deprecation import MiddlewareMixin
from django.db import OperationalError
from django.core.cache import cache
from django.conf import settings

from core.utils.schema import set_schema

logger = logging.getLogger(__name__)
_thread_locals = threading.local()

# Constants
CACHE_TIMEOUT = getattr(settings, "TENANT_CACHE_TIMEOUT", 3600)  # 1 hour default
LOCALHOST_HOSTS = {"localhost", "127.0.0.1"}
DEFAULT_SCHEMA = "public"  # Fallback schema for local/sqlite
API_TIMEOUT = 5  # Seconds for API requests


class TenantMiddleware(MiddlewareMixin):
    """
    Middleware for handling multi-tenancy based on subdomains.

    - On localhost/127.0.0.1: ignore tenant logic, force schema="public".
    - On other hosts: extract schema from subdomain, validate via Lago API, cache tenant.
    - Sets schema on request and thread-local, calls set_schema().
    - Redirects to default URL when tenant is invalid/inactive or on DB errors.
    """

    async_mode = False  # required for Django 5.x

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response
        self.api_key: Optional[str] = getattr(settings, "LAGO_API_KEY", None)
        self.api_url: str = getattr(settings, "LAGO_API_URL", "http://lago:3000")
        self.default_redirect: str = getattr(
            settings,
            "DEFAULT_TENANT_REDIRECT_URL",
            "http://payday.cd",
        )

        if not self.api_key:
            logger.warning("LAGO_API_KEY not configured – tenant validation will be skipped.")

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        host = request.get_host().split(":")[0]  # Exclude port

        # 1) Local development: always use public schema, ignore multi-tenancy
        if host in LOCALHOST_HOSTS:
            logger.debug("Localhost detected (%s) – forcing schema '%s'", host, DEFAULT_SCHEMA)
            request.schema = DEFAULT_SCHEMA
            _thread_locals.schema = DEFAULT_SCHEMA
            request.tenant = {"schema": DEFAULT_SCHEMA, "is_active": True}
            set_schema(DEFAULT_SCHEMA)
            return None

        # 2) Remote hosts: apply subdomain-based tenancy
        schema = self.extract_schema_from_host(host)
        if not self.is_valid_schema(schema):
            logger.warning("Invalid or missing schema from host: %s", host)
            return self.redirect_to_default("invalid-schema")

        tenant_info = self.get_or_fetch_tenant(schema)
        if not tenant_info or not tenant_info.get("is_active"):
            logger.warning("Tenant not found or inactive: %s", schema)
            return self.redirect_to_default("inactive-or-missing")

        request.schema = schema
        _thread_locals.schema = schema
        request.tenant = tenant_info
        set_schema(schema)

        return None

    def process_exception(self, request: HttpRequest, exception: Exception) -> Optional[HttpResponse]:
        """Handle exceptions gracefully, e.g., DB errors post-schema set."""
        if isinstance(exception, OperationalError):
            logger.error(
                "Database operational error after setting schema %s: %s",
                getattr(request, "schema", "unknown"),
                exception,
            )
            return self.redirect_to_default("db-error")
        return None

    def extract_schema_from_host(self, host: str) -> Optional[str]:
        """Extract subdomain as schema from host (e.g., foo.example.com -> 'foo')."""
        parts = host.split(".")
        return parts[0] if len(parts) > 1 else None

    def is_valid_schema(self, schema: Optional[str]) -> bool:
        """Validate schema – non-empty and not reserved like 'www'."""
        reserved = {"www", "api", "admin"}
        return bool(schema) and schema.lower() not in reserved

    def get_or_fetch_tenant(self, schema: str) -> Optional[dict]:
        """
        Retrieve tenant from cache; fetch from Lago API if missing; fallback on errors.
        """
        cache_key = f"tenant_{schema.lower()}"
        tenant = cache.get(cache_key)
        if tenant is not None:
            return tenant

        try:
            tenant = self.fetch_tenant_from_lago(schema)
            if tenant:
                cache.set(cache_key, tenant, timeout=CACHE_TIMEOUT)
                return tenant
        except Exception as e:
            logger.exception("Failed to fetch/cache tenant %s: %s", schema, e)

        # Fallback: still return a consistent structure, marked inactive
        return cache.get(cache_key) or {"schema": schema, "is_active": False}

    def fetch_tenant_from_lago(self, schema: str) -> Optional[dict]:
        """Fetch tenant subscription from Lago API with timeout and validation."""
        if not self.api_key:
            logger.error("Lago API key missing – cannot fetch tenants.")
            raise ValueError("LAGO_API_KEY required for tenant fetching.")

        try:
            response = requests.get(
                f"{self.api_url}/api/v1/subscriptions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                params={"external_customer_id": schema},
                timeout=API_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            subscriptions = data.get("subscriptions", [])

            active_statuses = {"active", "trialing", "in_trial"}
            active_subs = [s for s in subscriptions if s.get("status") in active_statuses]

            if not active_subs:
                logger.info("No active subscriptions for schema: %s", schema)
                return {"schema": schema, "is_active": False}

            first_sub = active_subs[0]
            tenant = {
                "schema": schema,
                "external_id": schema,
                "is_active": True,
                "created_at": first_sub.get("created_at"),
                "lago_customer_id": first_sub.get("lago_customer_id"),
                "subscription_status": first_sub.get("status"),
            }
            logger.debug("Fetched active tenant: %s", tenant)
            return tenant

        except requests.RequestException as e:
            logger.error("Lago API request failed for %s: %s", schema, e)
            raise

    def redirect_to_default(self, reason: str = "not-found") -> HttpResponseRedirect:
        """Redirect to default URL with reason query param."""
        url = f"{self.default_redirect}?message={reason}"
        logger.info("Redirecting to default: %s", url)
        return HttpResponseRedirect(url)

    @staticmethod
    def get_schema() -> Optional[str]:
        """Retrieve current schema from thread-local."""
        return getattr(_thread_locals, "schema", None)

    @staticmethod
    def get_tenant() -> dict:
        """Retrieve current tenant from cache using thread-local schema."""
        schema = TenantMiddleware.get_schema()
        if schema:
            return cache.get(f"tenant_{schema.lower()}", {})
        return {}
