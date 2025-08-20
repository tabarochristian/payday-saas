import requests
from django.shortcuts import render, redirect, get_list_or_404, get_object_or_404
from django.template.loader import render_to_string
from django.utils.translation import gettext as _
from django.template import Context, Template
from django.http import HttpResponse
from django.contrib import messages
from django.apps import apps

from core.views import BaseViewMixin
from core import models


class Print(BaseViewMixin):
    """
    A view that generates and returns a printed/exported version of model objects
    based on query parameters and a stored document template.

    Supports two formats:
      - HTML (default): renders objects using the template and displays them in-browser.
      - PDF: sends the HTML through Gotenberg for conversion to PDF.
    """

    action = ["view"]
    template_name = "print.html"

    def get(self, request, document, app, model, doctype='html'):
        """
        Handle GET requests to export data using a document template.

        Args:
            request (HttpRequest): Incoming HTTP request.
            document (str|int): Primary key of the document template.
            app (str): Django app label where the target model resides.
            model (str): Name of the target model class.
            doctype (str): Either "html" (default) or "pdf".

        Returns:
            HttpResponse: Rendered response (HTML or PDF).
        """

        # Build query parameters
        query_params = {}
        for key, value in request.GET.items():
            if "__in" in key:
                query_params[key] = [
                    v.strip() for v in value.split(",") if v.strip()
                ]
            else:
                query_params[key] = value

        if not query_params:
            messages.warning(request, _("Impossible de trouver le modèle d'objet"))
            return redirect(request.META.get("HTTP_REFERER", "/"))

        # Resolve model
        model_class = apps.get_model(app, model_name=model)
        objects = get_list_or_404(model_class, **query_params)

        # Get document template
        document_template = get_object_or_404(models.Template, pk=document)

        # Render each object individually
        rendered_outputs = []
        for obj in objects:
            context = Context({"object": obj})
            rendered_outputs.append(
                Template(document_template.content).render(context)
            )

        # Final context for the print view
        context = {
            "document_template": document_template,
            "objects": objects,
            "rendered_outputs": rendered_outputs,
        }

        # PDF export branch
        if doctype == "pdf":
            gotenberg_url = "http://gotenberg:3000/forms/chromium/convert/html"
            html_content = render_to_string(self.template_name, context)

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

        return render(request, self.template_name, context)
