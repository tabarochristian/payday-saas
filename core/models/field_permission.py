from crispy_forms.layout import Layout, Column, Fieldset, Row as CrispyRow
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from core.models import fields, Base

class FieldPermission(Base):
    created_by, updated_by = None, None

    user = fields.ModelSelectField(
        get_user_model(),
        verbose_name=_('utilisateur'),  # French verbose name
        help_text=_('L\'utilisateur auquel cette permission est attribuée.'),  # Help text
    )

    group = fields.ModelSelectField(
        "core.group",
        verbose_name=_('roles'),  # French verbose name
        help_text=_('Le groupe auquel cette permission est attribuée.'),  # Help text
    )

    content_type = fields.ModelSelectField(
        "contenttypes.contenttype",
        verbose_name=_('type de contenu'),  # French verbose name
        help_text=_('Le modèle auquel cette permission est associée.'),  # Help text
        inline=True
    )

    field_name = fields.CharField(
        max_length=100,
        verbose_name=_('nom du champ'),  # French verbose name
        help_text=_('Le nom du champ pour lequel la permission est définie.'),  # Help text
        inline=True
    )

    can_view = fields.BooleanField(
        default=False,
        verbose_name=_('en lecture seule'),  # French verbose name
        help_text=_('Indique si l\'utilisateur ou le groupe peut voir ce champ.'),  # Help text
        inline=True
    )

    can_edit = fields.BooleanField(
        default=False,
        verbose_name=_('peut modifier'),  # French verbose name
        help_text=_('Indique si l\'utilisateur ou le groupe peut modifier ce champ.'),  # Help text
        inline=True
    )

    list_display = ('user', 'content_type', 'field_name', 'can_view', 'can_edit')
    list_filter = ('content_type', 'group')

    layout = Layout(
        CrispyRow(
            Column('group'),
            Column('user'),
            Column('content_type'),
        ),
        Fieldset(
            _('Row'),
            CrispyRow(
                Column('field'),
                Column('value'),
            )
        ),
    )

    class Meta:
        unique_together = (
            ('user', 'content_type', 'field_name'),
            ('group', 'content_type', 'field_name'),
        )
        verbose_name = _('permission sur champ')  # French verbose name for the model
        verbose_name_plural = _('permissions sur champ')  # French verbose name for the model (plural)

    @property
    def name(self):
        return f"{self.content_type.model} | {self.field_name} | {self.user or self.group}"

    def __str__(self):
        return self.name