# payroll/views/slips.py

from django.utils.translation import gettext_lazy as _
from django.template.loader import render_to_string
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.http import Http404
from django.apps import apps
from core.views import Read

import requests
import logging

logger = logging.getLogger(__name__)


class Slips(Read):
    """
    A view that displays payslip information for paid employees.

    Features:
      - Uses locals() only where safe (template rendering)
      - Dynamic model loading via apps.get_model()
      - Raises 404 if no records match filters
      - Safe filtering using query params
    """
    template_name = "payroll/slip.html"

    @property
    def model_class(self):
        """Return the model class from URL kwargs."""
        return apps.get_model("payroll", model_name="paidemployee")

    def get(self, request, doctype='html'):
        """
        Handle GET requests to display payslips.
        """
        logger.info("User %s requested payslip(s)", request.user)

        # Set app/model context
        self.kwargs.update({"app": "payroll", "model": "paidemployee"})

        try:
            # Load model dynamically
            model_class = self.model_class
            logger.debug(f"Loaded model: {model_class.__name__}")

            # Extract and sanitize query parameters
            query_params = {
                key: value.split(',') if "__in" in key else value
                for key, value in request.GET.items() if value
            }

            logger.debug("Applying query filters: %s", query_params)
            qs = self.get_queryset().filter(**query_params)
            sub_organization = self.sub_organization()

            if not qs.exists():
                logger.warning("No payslips matched the filters")
                raise Http404(_("Aucun bulletin de paie trouvé avec ces filtres"))

            # PDF export branch
            if doctype == "pdf":
                gotenberg_url = "http://gotenberg:3000/forms/chromium/convert/html"
                html_content = render_to_string(self.template_name, locals())

                try:
                    resp = requests.post(
                        gotenberg_url,
                        files={
                            "index.html": ("index.html", html_content, "text/html")
                        }
                    )
                    resp.raise_for_status()
                except requests.RequestException as exc:
                    messages.error(
                        request,
                        _("Erreur lors de la génération du PDF : %(err)s") % {"err": str(exc)},
                    )
                    return redirect(request.META.get("HTTP_REFERER", "/"))

                response = HttpResponse(resp.content, content_type="application/pdf")
                response["Content-Disposition"] = 'inline; filename="preview.pdf"'
                return response
            return render(request, self.template_name, locals())

        except LookupError as e:
            logger.error("Model lookup failed: %s", str(e), exc_info=True)
            raise Http404(_("Modèle introuvable")) from e

        except Exception as e:
            logger.exception("Unexpected error in Slips view: %s", str(e))
            raise Http404(_("Une erreur est survenue lors du chargement des fiches"))