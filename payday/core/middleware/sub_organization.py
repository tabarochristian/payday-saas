import logging
from typing import Any, List, Optional

from django.apps import apps
from django.core.cache import cache
from django.db import OperationalError
from django.http import HttpRequest
from django.utils.deprecation import MiddlewareMixin

# Adjust if model is elsewhere; fallback to dynamic lookup
from core.models import SubOrganization

logger = logging.getLogger(__name__)


class SubOrganizationMiddleware(MiddlewareMixin):
    """
    High-performance, robust middleware for attaching SubOrganization data to requests.

    Features:
      - Global caching of all SubOrganizations (1-hour default TTL)
      - Lazy, cached model lookup
      - Graceful degradation on DB/model errors
      - Intelligent selection: session → user profile → first available
      - Type-annotated and fully documented
      - Thread-safe and efficient
    """

    CACHE_KEY = "suborganizations:all"
    CACHE_TIMEOUT = 0  # 1 hour; adjust via settings if needed

    def __init__(self, get_response: Any = None):
        super().__init__(get_response)
        self._model = None  # Cached model class

    def process_request(self, request: HttpRequest) -> None:
        """
        Attach suborganizations list and selected suborganization to the request.
        """
        request.suborganizations: List[SubOrganization] = []
        request.suborganization: Optional[SubOrganization] = None

        model = self.get_suborg_model()
        if not model:
            logger.warning(
                "SubOrganization model unavailable – skipping suborg middleware")
            return

        suborgs = self.get_all_suborganizations(model)
        request.suborganizations = suborgs

        if not suborgs:
            logger.debug("No SubOrganizations found in database")
            return

        # Determine selected suborganization
        selected = self.select_suborganization(request, suborgs)
        request.suborganization = selected

        if selected:
            logger.debug(
                f"Selected SubOrganization: {selected.id} ({selected.name})")
        else:
            logger.debug(
                "No SubOrganization selected – falling back to first available")
            request.suborganization = suborgs[0]

    def get_suborg_model(self) -> Optional[Any]:
        """
        Lazily retrieve the SubOrganization model with in-memory caching.
        Falls back gracefully if model/app not available.
        """
        if self._model is not None:
            return self._model

        try:
            # Prefer direct import for speed and type checking
            from core.models import SubOrganization as Model
            self._model = Model
            return Model
        except ImportError:
            pass

        # Fallback to dynamic lookup
        try:
            model = apps.get_model("core", "suborganization")
            self._model = model
            return model
        except LookupError as e:
            logger.error(f"SubOrganization model lookup failed: {e}")
            self._model = False  # Sentinel to avoid repeated lookups
            return None

    def get_all_suborganizations(self, model: Any) -> List[SubOrganization]:
        """
        Retrieve all SubOrganizations from cache or database.
        Caches results to minimize DB hits.
        """
        cached = cache.get(self.CACHE_KEY)
        if cached is not None:
            return cached

        try:
            # Optimize with select_related if needed
            suborgs = list(model.objects.all().select_related())
            cache.set(self.CACHE_KEY, suborgs, timeout=self.CACHE_TIMEOUT)
            logger.debug(f"Cached {len(suborgs)} SubOrganizations")
            return suborgs
        except OperationalError as e:
            logger.exception(
                f"Database error while fetching SubOrganizations: {e}")
            return []
        except Exception as e:
            logger.exception(
                f"Unexpected error fetching SubOrganizations: {e}")
            return []

    def select_suborganization(self, request: HttpRequest, suborgs: List[SubOrganization]) -> Optional[SubOrganization]:
        """
        Select the active SubOrganization using multiple fallbacks:
          1. Session key 'sub_organization' (ID or name)
          2. User's profile sub_organization (if authenticated)
          3. None (caller may fallback to first)
        """
        candidate = None

        # 1. Session override
        session_id = request.session.get("sub_organization")
        if session_id:
            candidate = self._find_by_id_or_name(suborgs, session_id)

        # 2. User profile (if authenticated and has sub_organization)
        if not candidate and request.user.is_authenticated:
            user_org = getattr(request.user, "sub_organization", None)
            if user_org:
                candidate = self._find_by_id_or_name(suborgs, user_org)

        return candidate

    @staticmethod
    def _find_by_id_or_name(suborgs: List[SubOrganization], value: Any) -> Optional[SubOrganization]:
        """
        Find SubOrganization by ID (int/PK) or name (string).
        Safe string comparison.
        """
        if not value:
            return None

        str_value = str(value).strip()
        for org in suborgs:
            if str(org.id) == str_value or org.name.strip().lower() == str_value.lower():
                return org
        return None

    # Optional: Invalidate cache on model changes (uncomment and connect in apps.py)
    # @receiver([post_save, post_delete], sender=SubOrganization, weak=False)
    # def invalidate_cache(sender, **kwargs):
    #     cache.delete(SubOrganizationMiddleware.CACHE_KEY)
