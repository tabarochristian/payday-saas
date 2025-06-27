from crispy_forms.layout import Layout, Row, Column
from django.urls import reverse_lazy

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext as _
from django.db import models

from core.models.managers import UserManager
from core.models import fields
from django.apps import apps

class User(AbstractUser):
    first_name, last_name, username = None, None, None
    
    updated_at = fields.DateTimeField(
        verbose_name=_('mis à jour le/à'), 
        auto_now=True
    )
    created_at = fields.DateTimeField(
        verbose_name=_('créé le/à'), 
        auto_now_add=True
    )

    email = fields.EmailField(
        unique=True, 
        db_index=True, 
        verbose_name=_('email')
    )

    password = models.CharField(
        _("password"), 
        max_length=128,
        editable=False
    )

    groups = fields.ModelSelect2Multiple(
        "core.group",
        verbose_name=_("groups"),
        blank=True,
        help_text=_(
            "The groups this user belongs to. A user will get all permissions "
            "granted to each of their groups."
        )
    )

    user_permissions = fields.ModelSelect2Multiple(
        "auth.permission",
        verbose_name=_("user permissions"),
        blank=True,
        help_text=_("Specific permissions for this user."),
    )
    
    USERNAME_FIELD = 'email'
    objects = UserManager()
    REQUIRED_FIELDS = ()
    
    inlines = ('core.columnlevelsecurity', 'core.rowlevelsecurity')
    list_display = ('id', 'email', 'is_active')
    
    search_fields = ('id', 'email',)
    list_filter = ('is_active',)
    
    layout = Layout(
        Column('email'),
        Row(
            Column('groups'),
            Column('user_permissions')
        ),
        Row(
            Column('is_staff'),
            Column('is_active'),
            Column('is_superuser')
        )
    )

    def __str__(self):
        return self.name

    @property
    def name(self):
        return self.email

    def get_full_name(self):
        return self.name
    
    def notify(self, _from, subject, message, *args, **kwargs):
        notification = apps.get_model('core', 'notification')
        return notification.objects.create(_from=_from, _to=self, subject=subject, message=message)
    
    def get_user_rls(self, app, model, *args, **kwargs):
        if self.is_superuser:
            return {}

        RowLevelSecurity = apps.get_model('core', model_name='rowlevelsecurity')
        groups = self.groups.all() or []

        rls_rules = (
            RowLevelSecurity.objects
            .filter(
                content_type__app_label = app,
                content_type__model = model,
            ).filter(
                models.Q(user=self) | models.Q(group__in=groups)
            )
            .values_list('field', 'value')
        )

        return {field: value for field, value in rls_rules}
    
    def get_user_field_permission(self, app, model, *args, **kwargs):
        if self.is_superuser:
            return {}
        
        groups = self.groups.all() or []
        columnlevelsecurity = apps.get_model('core', 'columnlevelsecurity')

        fields = columnlevelsecurity.objects.filter(
            content_type__app_label = app,
            content_type__model = model
        ).filter(
            models.Q(user=self) | models.Q(group__in=groups)
        ).values('field', 'can_view')
        return {item['field']: item['can_view'] for item in fields}

    def get_absolute_url(self):
        return reverse_lazy(
            'core:change', 
            kwargs={'app': self._meta.app_label, 'model': self._meta.model_name, 'pk': self.pk}
        )
