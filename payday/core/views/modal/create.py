from django.http import HttpResponse
from core.views.base import Create

class CreateModal(Create):
    """
    A modal variant of the Create view.

    This view is intended for usage in modal dialogs. It overrides the standard 
    'next' behavior to return an HTTP 204 response with an HTMX trigger header,
    indicating that a change has occurred on the frontend. It also specifies 
    a modal-specific template for creating new objects.

    Attributes:
        next (HttpResponse): The response returned after a successful create action,
                             sending a 204 No Content status with an HTMX 'changed' trigger.
        template_name (str): The template to be used for rendering the modal.
    """
    # Set the "next" response to HTTP 204 with an HTMX trigger header.
    next = HttpResponse(status=204, headers={'HX-Trigger': 'changed'})
    # Specify the modal-specific template for object creation.
    template_name = "modal/create.html"
