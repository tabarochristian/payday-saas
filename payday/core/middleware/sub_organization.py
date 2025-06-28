import logging

from django.apps import apps
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

class SubOrganizationMiddleware(MiddlewareMixin):
    """
    Middleware that loads all SubOrganizations and attaches them to the request,
    along with the selected one based on session data.
    """

    CACHE_KEY = "all_suborganizations"
    CACHE_TIMEOUT = getattr(settings, "SUBORG_CACHE_TIMEOUT", 300)  # 5 minutes

    def process_request(self, request):
        request.suborganizations = []
        request.suborganization = None

        # Load model
        SubOrganization = self.get_suborg_model()
        if not SubOrganization:
            return

        # Get all suborgs (optionally cached)
        suborgs = self.get_all_suborganizations(SubOrganization)
        request.suborganizations = suborgs

        # Get selected suborg ID from session
        selected = request.session.get(
            "sub_organization",
            getattr(request.user, "sub_organization", None)
        )

        selected = (
            next((s for s in suborgs if str(s.id) == str(selected) or s.name == selected), None)
            if selected
            else None
        )

        request.suborganization = selected

    def get_all_suborganizations(self, SubOrganization):
        """
        Returns all SubOrganization instances, optionally from cache.
        """
        if settings.DEBUG:
            return list(SubOrganization.objects.all())

        cached = cache.get(self.CACHE_KEY)
        if cached is not None:
            return cached

        try:
            suborgs = list(SubOrganization.objects.all())
            cache.set(self.CACHE_KEY, suborgs, timeout=self.CACHE_TIMEOUT)
            return suborgs
        except Exception as e:
            logger.exception("Failed to load SubOrganizations")
            return []

    def get_suborg_model(self):
        """
        Dynamically retrieves the SubOrganization model.
        """
        try:
            return apps.get_model("core", "SubOrganization")
        except LookupError as e:
            logger.error(f"SubOrganization model not found: {e}")
            return None
