from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from crispy_forms.layout import Layout
from core.models import fields, Base
from django.db import models

class Workflow(Base):
    status = None
    name = fields.CharField(_('nom'), max_length=100)
    content_type = fields.ModelSelectField(
        "contenttypes.contenttype",
        on_delete=models.CASCADE, 
        verbose_name=_('modèle associé')
    )
    condition = fields.AceField(
        mode='python',
        verbose_name=_('condition applicable à ce workflow'),
        default='True'
    )
    users = fields.ModelSelect2Multiple(
        get_user_model(),
        verbose_name=_("validateur(s)")
    )

    layout = Layout('name', 'content_type', 'condition', 'users')
    list_display = ('id', 'name', 'content_type', 'condition')

    class Meta:
        verbose_name_plural = _('workflows')
        verbose_name = _('workflow')
