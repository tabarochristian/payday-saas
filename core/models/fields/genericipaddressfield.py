from django.db import models

class GenericIPAddressField(models.GenericIPAddressField):
    def __init__(self, *args, **kwargs):
        self.inline = kwargs.pop('inline', False)
        super().__init__(*args, **kwargs)
