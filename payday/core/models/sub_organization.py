from django.utils.translation import gettext as _
from crispy_forms.layout import Layout
from core.models import Base, fields

class SubOrganization(Base):
    name = fields.CharField(
        verbose_name=_('nom'),
        max_length=100
    )

    list_display = ('id', 'name')
    layout = Layout('name',)

    class Meta:
        verbose_name = _('sous-organisation')
        verbose_name_plural = _('sous-organisation(s)')