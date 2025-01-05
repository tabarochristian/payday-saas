from django.db import models

class NullBooleanField(models.NullBooleanField):
    def __init__(self, *args, **kwargs):
        self.inline = kwargs.pop('inline', False)
        self.level = kwargs.pop('level', 0)
        super().__init__(*args, **kwargs)
