# payroll/views/slips.py

from django.utils.translation import gettext_lazy as _
from django.shortcuts import render
from django.http import Http404
from django.apps import apps
from django.db.models import Model
from core.views import BaseView
import logging

logger = logging.getLogger(__name__)


class Slips(BaseView):
    """
    A view that displays payslip information for paid employees.

    Features:
      - Dynamic model loading via apps.get_model()
      - Safe filtering using query params
      - Raises 404 if no records match filters
      - Uses locals() only where safe (template rendering)
    """
    template_name = "payroll/slip.html"

    def get(self, request):
        """
        Handle GET requests to display payslips.
        """
        logger.info("User %s requested payslip(s)", request.user)

        # Set app/model context
        app = "payroll"
        model_name = "paidemployee"
        self.kwargs.update({"app": app, "model": model_name})

        try:
            # Load model dynamically
            model_class = apps.get_model(app, model_name)
            logger.debug(f"Loaded model: {model_class.__name__}")

            # Extract and sanitize query parameters
            query_params = {
                key: value.split(',') if "__in" in key else value
                for key, value in request.GET.items() if value
            }

            logger.debug("Applying query filters: %s", query_params)

            # Apply filters
            qs = model_class.objects.filter(**query_params)

            if not qs.exists():
                logger.warning("No payslips matched the filters")
                raise Http404(_("Aucun bulletin de paie trouvé avec ces filtres"))

            return render(request, self.template_name, locals())

        except LookupError as e:
            logger.error("Model lookup failed: %s", str(e), exc_info=True)
            raise Http404(_("Modèle introuvable")) from e

        except Exception as e:
            logger.exception("Unexpected error in Slips view: %s", str(e))
            raise Http404(_("Une erreur est survenue lors du chargement des fiches"))