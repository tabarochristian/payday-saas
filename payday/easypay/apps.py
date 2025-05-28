from django.apps import AppConfig


class EasypayConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "easypay"

    def ready(self):
        import easypay.signals