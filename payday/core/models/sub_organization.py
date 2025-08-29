from django.utils.translation import gettext as _
from core.utils import upload_directory_file
from crispy_forms.layout import Layout
from core.models import Base, fields
import base64

class SubOrganization(Base):
    sub_organization, status = None, None
    logo = fields.ImageField(
        verbose_name=_('logo'),
        help_text=_('Logo de la sous-organisation - Dimension 64x64'),
        upload_to=upload_directory_file,
        default=None,
        blank=True,
        null=True
    )

    name = fields.CharField(
        verbose_name=_('nom'),
        max_length=100
    )

    def logo_base64(self):
        if not self.logo:
            return None

        try:
            with self.logo.open('rb') as image_file:
                image_bytes = image_file.read()
                base64_str = base64.b64encode(image_bytes).decode('utf-8')
                mime_type = self.logo.file.content_type
                return f"data:{mime_type};base64,{base64_str}"
        except Exception as e:
            # Optional: log the error or handle it gracefully
            return None

    list_display = ('id', 'name')
    layout = Layout('logo', 'name', '_metadata')

    class Meta:
        verbose_name = _('sous-organisation')
        verbose_name_plural = _('sous-organisation(s)')