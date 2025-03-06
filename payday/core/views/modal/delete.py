from django.http import HttpResponse
from core.views.base import Delete

class DeleteModal(Delete):
    """
    A modal variant of the Delete view.

    This view is designed for use in modal dialogs. It modifies the standard 
    Delete view's behavior by overriding the 'next' attribute to return an HTTP 
    204 response with an HTMX trigger header. This header ("HX-Trigger": "changed")
    is used by HTMX on the frontend to signal that a change has occurred (e.g., an 
    object has been deleted), so the client can respond accordingly without reloading 
    the page.

    Attributes:
        next (HttpResponse): A predefined HTTP 204 (No Content) response with an 
                             HTMX trigger header, used to notify the client of successful deletion.
        template_name (str): The path to the modal-specific template used for rendering the delete confirmation.
    """
    # Override the 'next' attribute to send a 204 response with the HTMX trigger.
    next = HttpResponse(status=204, headers={'HX-Trigger': 'changed'})
    
    # Use the modal-specific template for showing the delete confirmation.
    template_name = "modal/delete.html"
