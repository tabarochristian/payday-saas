from phonenumber_field.modelfields import PhoneNumberField
from django.utils.translation import gettext as _
from django.db import models
import re

def clean_string(input_string):
    cleaned_string = re.sub(r'[^A-Za-z\s]', '', input_string)
    cleaned_string = cleaned_string.lower()
    return cleaned_string


class Tenant(models.Model):
    first_name = models.CharField(
        _('first name'),
        max_length=50
    )

    last_name = models.CharField(
        _('last name'),
        max_length=50
    )

    name = models.CharField(
        _('organization\'s name'), 
        max_length=50,
        unique=True
    )
    
    email = models.EmailField(
        _('email'), 
        max_length=50,
        unique=True
    )
    phone = PhoneNumberField(
        _('phone'),
        help_text=_('+243 8XX XXX XXX'),
        unique=True
    )

    size = models.CharField(
        _("size of organization"),
        max_length=50,
        choices=(
            (None, '-'),
            ('1-10', '1-10'), 
            ('11-50', '11-50'), 
            ('51-200', '51-200'), 
            ('201-500', '201-500'), 
            ('501-1000', '501-1000'), 
            ('1001+', '1001+')
        ),
        help_text=_('This information helps us tailor our services to better meet your needs.')
    )
    schema = models.CharField(
        _('schema'), 
        max_length=50,
        editable=False,
        unique=True
    )
    is_active = models.BooleanField(
        _('is active'), 
        max_length=50,
        editable=False,
        default=False
    )

    updated_at = models.DateTimeField(
        verbose_name=_('mis à jour le/à'), 
        auto_now=True,
        editable=False
    )
    created_at = models.DateTimeField(
        verbose_name=_('créé le/à'), 
        auto_now_add=True,
        editable=False
    )

    @property
    def serialized(self):
        data = {field.name:getattr(self, field.name, None) for field in Tenant._meta.fields}
        data['phone'] = data['phone'].as_e164
        return data

    @property
    def full_name(self):
        return f"{self.last_name} {self.first_name}"
    
    def save(self, *args, **kwargs):
        self.schema = clean_string(self.name)
        return super().save()

    class Meta:
        db_table = 'tenant'
        verbose_name = _('tenant')
        unique_together = ('name', 'phone')
        verbose_name_plural = _('tenant(s)')
