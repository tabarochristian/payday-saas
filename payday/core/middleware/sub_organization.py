from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.apps import apps
import logging

logger = logging.getLogger(__name__)

class SubOrganizationMiddleware(MiddlewareMixin):
    """
    Middleware that loads all SubOrganizations and attaches them to the request,
    along with the selected one based on session data.
    """

    def process_request(self, request):
        request.suborganizations = []
        request.suborganization = None

        # Load model
        SubOrganization = self.get_suborg_model()
        if not SubOrganization:
            return

        # Get all suborgs directly from the database
        suborgs = self.get_all_suborganizations(SubOrganization)
        request.suborganizations = suborgs

        # Get selected suborg ID from session
        user_org = getattr(request.user, "sub_organization", None)
        selected = request.session.get("sub_organization", None)
        selected = selected or user_org

        selected = (
            next((s for s in suborgs if str(s.id) == str(selected) or s.name == selected), None)
            if selected
            else None
        )

        request.suborganization = selected

    def get_all_suborganizations(self, model):
        """
        Returns all SubOrganization instances directly from the database.
        """
        try:
            return list(model.objects.all())
        except Exception as e:
            logger.exception("Failed to load SubOrganizations")
            return []

    def get_suborg_model(self):
        """
        Dynamically retrieves the SubOrganization model.
        """
        try:
            return apps.get_model("core", "suborganization")
        except LookupError as e:
            logger.error(f"SubOrganization model not found: {e}")
            return None
