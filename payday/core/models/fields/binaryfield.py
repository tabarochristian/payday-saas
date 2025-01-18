from django.db import models

class BinaryField(models.BinaryField):
    def __init__(self, *args, **kwargs):
        self.inline = kwargs.pop('inline', False)
        super().__init__(*args, **kwargs)
