from crispy_forms.layout import Layout, Column, Fieldset, Row as CrispyRow
from django.utils.translation import gettext as _
from core.models import Base, fields

class RowLevelSecurity(Base):
    updated_by, created_by = None, None

    user = fields.ModelSelectField(
        'core.user',
        verbose_name=_("utilisateur"),
        related_name='rows',
        inline=False,
        help_text=_("L'utilisateur auquel cette règle de sécurité s'applique."),  # Help text
    )

    group = fields.ModelSelectField(
        "core.group",
        verbose_name=_('roles'),  # French verbose name
        help_text=_('Le groupe auquel cette permission est attribuée.'),  # Help text
    )

    content_type = fields.ForeignKey(
        'contenttypes.contenttype',
        verbose_name=_("type de contenu"),
        limit_choices_to={
            'app_label__in': ['core', 'employee', 'payroll']
        },
        related_name='rows',
        inline=True,
        help_text=_("Le modèle auquel cette règle de sécurité est associée."),  # Help text
    )

    field = fields.CharField(
        verbose_name=_("champ"),
        max_length=255,
        inline=True,
        level=1,
        help_text=_("Le champ auquel cette règle de sécurité s'applique."),  # Help text
    )

    value = fields.CharField(
        verbose_name=_("valeur"),
        max_length=255,
        inline=True,
        help_text=_("La valeur du champ à laquelle cette règle de sécurité s'applique."),  # Help text
    )

    list_display = ('user', 'content_type', 'field', 'value')
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

    def name(self):
        return f"{self.user} - {self.content_type}"

    class Meta:
        unique_together = ("content_type", "user", "field")
        verbose_name = _("sécurité au niveau de la ligne")
        verbose_name_plural = _("sécurités au niveau de la ligne")