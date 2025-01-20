# models.py
from django.core.files.images import get_image_dimensions
from django.utils.translation import gettext_lazy as _
from django.forms.widgets import ClearableFileInput
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from django.db import models
from PIL import Image

def validate_image_dimensions(image):
    """
    Validates that an image is exactly 480x640 pixels.
    """
    try:
        with Image.open(image) as img:
            width, height = img.size
            if width != 480 or height != 640:
                raise ValidationError(
                    _("The image must be exactly 480x640 pixels.")
                )
    except (TypeError, AttributeError, IOError):
        raise ValidationError(
            _("The uploaded file is not a valid image.")
        )

class PhotoPreviewField(models.ImageField):
    """
    Custom ImageField that validates image dimensions and provides a preview widget.
    """
    def __init__(self, *args, **kwargs):
        self.inline = kwargs.pop('inline', False)
        kwargs['validators'] = [validate_image_dimensions]
        super().__init__(*args, **kwargs)