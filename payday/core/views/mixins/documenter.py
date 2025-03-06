from core.models import Template

class DocumentMixin:
    """
    Mixin to provide functionality for retrieving document templates
    associated with the current model. Assumes that the implementing
    class provides a `get_model()` method.
    """

    def documents(self):
        """
        Retrieve Template documents for the current model based on the
        model's content type (i.e. the app label and model name).

        Returns:
            A QuerySet of Template objects filtered by the current model's
            content type.
        """
        model_class = self.get_model()  # Expecting the implementing class to define get_model()
        return Template.objects.filter(
            content_type__app_label=model_class._meta.app_label,
            content_type__model=model_class._meta.model_name
        )
