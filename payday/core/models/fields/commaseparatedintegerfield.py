from django.db import models

class CommaSeparatedIntegerField(models.CommaSeparatedIntegerField):
    def __init__(self, *args, **kwargs):
        self.inline = kwargs.pop('inline', False)
        super().__init__(*args, **kwargs)
