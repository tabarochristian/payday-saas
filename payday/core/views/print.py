import re
import pandas as pd
from django.shortcuts import render, redirect, get_list_or_404, get_object_or_404
from django.utils.translation import gettext as _
from django.template import Context, Template
from django.contrib import messages
from django.apps import apps

from core import models
from core.views import BaseView


class Print(BaseView):
    """
    A view that generates and returns a printed/exported version of model objects
    based on the selected query parameters and a document template.

    The view builds a query dictionary from the GET parameters, retrieves a list of 
    objects from the specified model, fetches a document template by its PK, and then
    renders the template for each object with a custom context. The rendered outputs are 
    then passed to a print template.
    """
    action = ["view"]
    template_name = "print.html"

    def get(self, request, document, app, model):
        """
        Handle GET requests to export data using a document template.
        
        Args:
            request (HttpRequest): Incoming HTTP request.
            document (str/int): Primary key of the document template.
            app (str): Application label where the target model resides.
            model (str): Name of the target model.
        
        Returns:
            HttpResponse: The rendered response with the printed view.
        """
        # Build a query dictionary from GET parameters.
        # For any parameter containing '__in', split its value by commas.
        query_params = {
            key: value.split(',') if '__in' in key else value
            for key, value in request.GET.items()
        }
        if not query_params:
            messages.warning(request, _("Impossible de trouver le modèle d'objet"))
            return redirect(request.META.get('HTTP_REFERER'))

        # Retrieve the model class using Django's apps registry.
        model_class = apps.get_model(app, model_name=model)
        # Get a list of objects matching the query; raise 404 if none found.
        object_list = get_list_or_404(model_class, **query_params)

        # Retrieve the document template; get_object_or_404 will raise a 404 if not found.
        document_template = get_object_or_404(models.Template, pk=document)

        # Render the template for each object.
        # Instead of using locals(), we explicitly build the context for each rendering.
        rendered_outputs = []
        for obj in object_list:
            # Build a context that can be extended later if needed.
            context = Context({
                'object': obj,
            })
            rendered_output = Template(document_template.content).render(context)
            rendered_outputs.append(rendered_output)

        return render(request, self.template_name, locals())
