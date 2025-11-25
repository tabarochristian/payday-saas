import logging
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django.apps import apps
from django.db import models
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from django.db.models import Q, ForeignKey

logger = logging.getLogger(__name__)

class Annotate(APIView):
    """
    API View to dynamically apply aggregation functions on model fields with enforced permissions.
    """

    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    UserModel = get_user_model()

    def get_queryset(self):
        """Retrieve queryset dynamically while enforcing permission checks."""
        # Enforce view permission for the model
        model_class = self.get_model_class()
        if not self.request.user.has_perm(f"{model_class._meta.app_label}.view_{model_class.__name__.lower()}"):
            logger.warning(f"Permission denied: User '{self.request.user}' lacks view access for '{model_class.__name__}'.")
            raise PermissionDenied(f"You do not have permission to view '{model_class.__name__}' data.")

        # Superusers and staff can access all records
        if self.request.user.is_superuser or self.request.user.is_staff:
            logger.info(f"User '{self.request.user}' has full access to '{model_class.__name__}'.")
            return model_class.objects.all()

        # Identify fields related to the user model
        user_related_fields = [
            field.name for field in model_class._meta.get_fields()
            if isinstance(field, ForeignKey) and field.related_model == self.UserModel
        ]

        # Restrict regular users to their own related data
        query_filter = Q()
        for field in user_related_fields:
            query_filter |= Q(**{field: self.request.user})

        logger.info(f"User '{self.request.user}' is restricted to their own related data in '{model_class.__name__}'.")
        return model_class.objects.filter(query_filter)
    
    def get_model_class(self):
        app, model = self.kwargs['app'], self.kwargs['model']
        return apps.get_model(app, model)

    def get(self, request, function, app, model, field):
        """Handles annotation requests with permission enforcement, validation, and logging."""
        try:
            # Validate model existence
            model_class = apps.get_model(app, model)
        except LookupError:
            logger.error(f"Model '{model}' in app '{app}' not found.")
            return Response({"error": f"Model '{model}' does not exist."}, status=404)

        # Validate field existence in the model
        if field not in [f.name for f in model_class._meta.fields]:
            logger.warning(f"Field '{field}' does not exist in model '{model}'.")
            return Response({"error": f"Field '{field}' does not exist."}, status=400)

        # Validate aggregation function existence
        try:
            aggregation_function = getattr(models, function)
            if not callable(aggregation_function):
                raise AttributeError
        except AttributeError:
            logger.warning(f"Invalid aggregation function '{function}'.")
            return Response({"error": f"Aggregation function '{function}' is invalid."}, status=400)

        try:
            # Retrieve filtered queryset with permission enforcement
            queryset = self.get_queryset()

            # Appy hard filter
            query = {
                k: v.split(",") if '__in' in k else v
                for k, v in request.GET.dict().items()
            }
            queryset = queryset.filter(**query)

            # Apply annotation function
            result = queryset.annotate(**{
                f"{field}__{function}": aggregation_function(field)
            })

            logger.info(f"Annotation '{function}' applied successfully on field '{field}' in '{model}'.")
            return Response({"result": list(result.values(field, "aggregated_value"))})

        except PermissionDenied as ex:
            logger.error(f"Permission error: {str(ex)}")
            return Response({"error": str(ex)}, status=403)

        except Exception as ex:
            logger.error(f"Error applying annotation: {str(ex)}", exc_info=True)
            return Response({"error": "Failed to apply annotation."}, status=500)