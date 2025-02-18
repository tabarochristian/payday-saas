from phonenumber_field.modelfields import PhoneNumberField
from django.utils.translation import gettext as _
from django.db import models
import re, json

def clean_string(input_string):
    cleaned_string = re.sub(r'[^A-Za-z\s]', '', input_string)
    cleaned_string = cleaned_string.lower().replace(' ','')
    return cleaned_string

class TenantPlan(models.TextChoices):
    BASIC = json.dumps({
        "name": "basic",
        "description": "Essentielle",
        "price": 0,
        "currency": "USD",
        "apps": {
            "employee": {
                "max": 100
            },
            "payroll": {
                "max": 1
            },
        }
    }), _('Essentielle')

class Tenant(models.Model):
    first_name = models.CharField(
        _('votre prenom'),
        max_length=50
    )

    last_name = models.CharField(
        _('votre nom'),
        max_length=50
    )

    name = models.CharField(
        _('nom de l\'organisme'), 
        max_length=50,
        unique=True
    )
    
    email = models.EmailField(
        _('email'), 
        max_length=50,
        unique=True
    )

    phone = PhoneNumberField(
        _('numéro de téléphone mobile'),
        help_text=_('+243 8XX XXX XXX'),
        unique=True
    )

    plan = models.CharField(
        _("plan d'abonnement"),
        max_length=255,
        choices = TenantPlan.choices,
        default=TenantPlan.BASIC
    )

    schema = models.CharField(
        _('schema'), 
        max_length=50,
        editable=False,
        unique=True,
        help_text=_('Nom du schéma dans la base de données')
    )

    is_active = models.BooleanField(
        _('is active'),
        default=False,
        help_text=_('Définir si le compte est actif ou non')
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
        data = {field.name: getattr(self, field.name, None) for field in Tenant._meta.fields}
        data['plan'] = json.loads(data['plan'])
        data['phone'] = data['phone'].as_e164
        return data

    @property
    def full_name(self):
        return f"{self.last_name} {self.first_name}"
    
    def save(self, *args, **kwargs):
        self.schema = clean_string(self.name)
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name
    

    class Meta:
        verbose_name_plural = _('tenant(s)')
        unique_together = ('name', 'phone')
        verbose_name = _('tenant')