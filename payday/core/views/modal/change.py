from django.http import HttpResponse
from core.views.base import Change

class ChangeModal(Change):
    """
    A modal variant of the Change view.

    This view is specialized for use in modal dialogs. It redefines the 'next'
    attribute to return an HTTP 204 response with an HTMX trigger header indicating
    that a change has occurred. It also specifies a dedicated template for modal
    presentations.

    Attributes:
        next (HttpResponse): The response returned after a successful change,
                             triggering frontend HTMX behavior.
        template_name (str): The path to the template used for rendering the modal.
    """
    # Set the "next" response to a 204 No Content with a custom HTMX trigger header.
    next = HttpResponse(status=204, headers={'HX-Trigger': 'changed'})
    
    # Specify the modal-specific template.
    template_name = "modal/change.html"
