from django.db import models

class DecimalField(models.DecimalField):
    def __init__(self, *args, **kwargs):
        self.level = kwargs.pop('level', 0)
        self.inline = kwargs.pop('inline', False)
        super().__init__(*args, **kwargs)
