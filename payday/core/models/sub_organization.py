from django.utils.translation import gettext as _
from core.utils import upload_directory_file
from crispy_forms.layout import Layout
from core.models import Base, fields


class SubOrganization(Base):
    sub_organization = None
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

    list_display = ('id', 'name')
    layout = Layout('logo', 'name')

    class Meta:
        verbose_name = _('sous-organisation')
        verbose_name_plural = _('sous-organisation(s)')