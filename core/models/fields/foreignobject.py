from django.db import models

class ForeignObject(models.ForeignObject):
    def __init__(self, *args, **kwargs):
        self.inline = kwargs.pop('inline', False)
        self.level = kwargs.pop('level', 0)
        super().__init__(*args, **kwargs)
