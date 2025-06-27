from crispy_forms.layout import Column, Fieldset, Layout, Row as CrispyRow
from django.utils.translation import gettext as _
from django.contrib.auth import get_user_model
from core.models import Base, fields
from django.core.cache import cache


class RowLevelSecurity(Base):
    """
    Model to handle row-level security for users and groups.
    """
    updated_by, created_by = None, None

    user = fields.ModelSelectField(
        get_user_model(),
        verbose_name=_("utilisateur"),
        related_name='rows',
        inline=False,
        help_text=_("L'utilisateur auquel cette règle de sécurité s'applique."),
        editable=False
    )
    
    group = fields.ModelSelectField(
        "core.group",
        verbose_name=_('roles'),
        help_text=_('Le groupe auquel cette permission est attribuée.'),
        editable=False
    )
    
    content_type = fields.ForeignKey(
        'contenttypes.contenttype',
        verbose_name=_("type de contenu"),
        limit_choices_to={'app_label__in': ['core', 'employee', 'payroll']},
        inline=True,
        help_text=_("Le modèle auquel cette règle de filtrage est associée."),
    )
    
    field = fields.CharField(
        verbose_name=_("champ"),
        max_length=255,
        inline=True,
        help_text=_("Le champ auquel cette règle de sécurité s'applique."),
    )
    value = fields.CharField(
        verbose_name=_("valeur"),
        max_length=255,
        inline=True,
        help_text=_("La valeur du champ à laquelle cette règle de sécurité s'applique."),
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

    def get_fields(self):
        """
        Retrieve editable fields for models in allowed apps.
        """
        cache_key = 'row_level_security_fields'
        fields = cache.get(cache_key)
        if fields is not None:
            return fields

        from django.apps import apps
        allowed_apps = ['core', 'employee', 'payroll']
        disallowed_fields = ['id'] + [field.name for field in Base._meta.get_fields()]

        models = apps.get_models()
        fields = [
            (model._meta.verbose_name.title(), [
                (field.name, field.verbose_name.title())
                for field in model._meta.fields
                if field.name not in disallowed_fields and field.editable
            ])
            for model in models
            if model._meta.app_label in allowed_apps
        ]
        fields = [(model, fields) for model, fields in fields if fields]
        cache.set(cache_key, fields, timeout=60 * 60)
        return fields

    @property
    def name(self):
        """
        Return the name representation of the RowLevelSecurity instance.
        """
        return f"{self.user} - {self.content_type}"

    class Meta:
        verbose_name = _("Filtrage dynamique des lignes")
        verbose_name_plural = _("Filtrage dynamique des lignes")
        unique_together = (
            ('user', 'content_type', 'field'),
            ('group', 'content_type', 'field'),
        )