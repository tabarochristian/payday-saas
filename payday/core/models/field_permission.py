from crispy_forms.layout import Column, Fieldset, Layout, Row as CrispyRow
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from core.models import Base, fields
from django.core.cache import cache

class FieldPermission(Base):
    """
    Model to handle field permissions for users and groups.
    """
    created_by, updated_by = None, None

    user = fields.ModelSelectField(
        get_user_model(),
        verbose_name=_('utilisateur'),
        help_text=_('L\'utilisateur auquel cette permission est attribuée.'),
        editable=False
    )
    group = fields.ModelSelectField(
        "core.group",
        verbose_name=_('roles'),
        help_text=_('Le groupe auquel cette permission est attribuée.'),
        editable=False
    )
    field_content_type = fields.ForeignKey(
        'contenttypes.contenttype',
        verbose_name=_("type de contenu"),
        limit_choices_to={'app_label__in': ['core', 'employee', 'payroll']},
        inline=True,
        help_text=_("Le modèle auquel cette règle de filtrage est associée."),
    )
    field = fields.CharField(
        max_length=100,
        verbose_name=_('champ'),
        help_text=_('Le nom du champ pour lequel la permission est définie.'),
        inline=True,
    )
    can_view = fields.BooleanField(
        default=False,
        verbose_name=_('en lecture seule'),
        help_text=_('Indique si l\'utilisateur ou le groupe peut voir ce champ.'),
        inline=True,
    )
    can_edit = fields.BooleanField(
        default=False,
        verbose_name=_('peut modifier'),
        help_text=_('Indique si l\'utilisateur ou le groupe peut modifier ce champ.'),
        inline=True,
    )

    list_display = ('user', 'content_type', 'field', 'can_view', 'can_edit')
    list_filter = ('content_type', 'group')

    layout = Layout(
        CrispyRow(
            Column('group'),
            Column('user'),
            Column('field_content_type'),
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
        cache_key = 'field_permission_fields'
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
        cache.set(cache_key, fields, timeout=60 * 60)  # Cache for 1 hour
        return fields

    class Meta:
        unique_together = (
            ('user', 'field_content_type', 'field'),
            ('group', 'field_content_type', 'field'),
        )
        verbose_name = _('filtrage des champs')
        verbose_name_plural = _('filtrage des champs')

    @property
    def name(self):
        """
        Return the name representation of the FieldPermission instance.
        """
        return f"{self.field_content_type.model} | {self.field} | {self.user or self.group}"

    def __str__(self):
        return self.name
