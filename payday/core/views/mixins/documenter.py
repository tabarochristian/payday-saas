from core.models import Template

class DocumentMixin:
    def documents(self):
        model = self.get_model()
        return Template.objects.filter(
            content_type__app_label=model._meta.app_label,
            content_type__model=model._meta.model_name
        )