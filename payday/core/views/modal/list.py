from core.views.base import List

class ListModal(List):
    """
    A modal variant of the List view.

    This view is tailored for use in modal dialogs. It overrides the default
    template to use a modal-specific layout, allowing list content to be displayed
    within a modal window. All other behavior is inherited from the base List view.
    
    Attributes:
        template_name (str): Specifies the modal-specific template.
    """
    # Specify the modal template for list views.
    template_name = "modal/list.html"
