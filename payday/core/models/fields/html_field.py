from tinymce import models

class HTMLField(models.HTMLField):
    def __init__(self, *args, **kwargs):
        self.inline = kwargs.pop('inline', False)
        super().__init__(*args, **kwargs)