from phonenumber_field.modelfields import PhoneNumberField
from crispy_forms.layout import Layout, Row, Column, Div
from django.utils.translation import gettext as _
from crispy_forms.bootstrap import PrependedText

from django.urls import reverse_lazy
from django.db import models

from core.utils import upload_directory_file
from core.models import Base, fields
from employee.utils import *

GENDERS = (('MALE', _('HOMME')), ('FEMALE', _('FEMME')))
PAYMENT_METHODS = (('CASH', _('CASH')), ('BANK', _('BANK')), ('MOBILE MONEY', _('MOBILE MONEY')))
MARITAl_STATUS = (('MARRIED', _('MARIÉ')), ('SINGLE', _('CÉLIBATAIRE')), ('WIDOWER', _('VEUF')), ('DIVORCED', _('DIVORCÉ')))

class Employee(Base):
    social_security_number = fields.CharField(_('numéro de sécurité sociale'), max_length=50, blank=True, null=True, default=None)
    registration_number = fields.CharField(_('matricule'), max_length=50, help_text=_("Uniquement des chiffres, sans commencer par 0"))

    agreement = fields.ModelSelectField('employee.agreement', verbose_name=_('type de contrat'), on_delete=models.CASCADE)
    date_of_join = fields.DateField(_('date d\'engagement'), help_text='YYYY-MM-DD', null=True, default=None)
    date_of_end = fields.DateField(_('date de fin du contrat'), help_text='YYYY-MM-DD', blank=True, null=True, default=None)

    designation = fields.ModelSelectField('employee.designation', verbose_name=_('fonction'), blank=True, null=True, default=None, on_delete=models.SET_NULL)
    grade = fields.ModelSelectField('employee.grade', verbose_name=_('grade'), blank=True, null=True, default=None, on_delete=models.SET_NULL)

    # linked field
    subdirection = fields.ModelSelectField('employee.subdirection', verbose_name=_('sous-direction'), blank=True, null=True, on_delete=models.SET_NULL, default=None)
    direction = fields.ModelSelectField('employee.direction', verbose_name=_('direction'), blank=True, null=True, on_delete=models.SET_NULL, default=None)
    service = fields.ModelSelectField('employee.service', verbose_name=_('service'), blank=True, null=True, on_delete=models.SET_NULL, default=None)

    middle_name = fields.CharField(_('post-nom'), max_length=100, blank=True, null=True, default=None)
    first_name = fields.CharField(_('prénom'), max_length=100, blank=True, null=True, default=None)
    last_name = fields.CharField(_('nom'), max_length=100, blank=True, null=True, default=None)

    date_of_birth = fields.DateField(_('date de naissance'), help_text='YYYY-MM-DD', null=True, default=None)
    gender = fields.CharField(_('genre'), max_length=10, choices=GENDERS, blank=True, null=True, default=None)

    spouse_date_of_birth = fields.DateField(_('date de naissance du conjoint'), help_text='YYYY-MM-DD', blank=True, null=True, default=None)
    marital_status = fields.CharField(_('état civil'), max_length=12, choices=MARITAl_STATUS, blank=True, null=True, default=None)
    spouse = fields.CharField(_('conjoint'), max_length=100, blank=True, null=True, default=None)
   

    mobile_number = PhoneNumberField(_('numéro de téléphone mobile'), help_text=_("+243 XXX XXX XXX"), null=True, default=None)
    physical_address = fields.TextField(_('adresse physique'), blank=True, null=True, default=None)
    emergency_information = fields.TextField(_('informations d\'urgence'), null=True, default=None)

    branch = fields.ModelSelectField('employee.Branch', verbose_name=_('site'),  null=True, on_delete=models.SET_NULL, default=None)

    payment_method = fields.CharField(_('mode de paiement'), max_length=20, choices=PAYMENT_METHODS, blank=True, null=True, default=None)
    payment_account = fields.CharField(_('numéro de compte/paiement'), max_length=50, blank=True, null=True, default=None)
    payer_name = fields.CharField(_('nom du payeur'), max_length=50, null=True, default=None)

    comment = fields.TextField(_('commentaire'), blank=True, null=True, default=None)
    status = fields.ModelSelectField('employee.status', verbose_name=_('status'), null=True, on_delete=models.SET_NULL, default=None)

    list_filter = ('agreement', 'date_of_join', 'direction', 'branch', 'designation', 'gender', 'marital_status', 'branch', 'status')
    search_fields = ('registration_number', 'social_security_number', 'agreement__name',
                    'designation__name', 'grade__name', 'direction__name', 'subdirection__name',
                    'service__name', 'first_name', 'middle_name', 'last_name', 'spouse',
                    'mobile_number', 'physical_address', 'emergency_information',
                    'branch__name', 'payment_account', 'comment')
    list_display = ('registration_number', 'last_name', 'middle_name', 'designation', 'branch', 'status')

    inlines = ['employee.child',]

    layout = Layout(
        'photo',
        Row(
            Column('registration_number'),
            Column('social_security_number')
        ),
        Row(
            Column('agreement'),
            Column('date_of_join'),
            Column('date_of_end')
        ),
        Row(
            Column('direction'),
            Column('subdirection'),
            Column('service'),
        ),
        Row(
            Column('branch'),
            Column('grade'),
            Column('designation'),
        ),
        Row(
            Column('first_name'),
            Column('middle_name'),
            Column('last_name'),
        ),
        Row(
            Column('date_of_birth'),
            Column('gender'),
        ),
        Row(
            Column('marital_status'),
            Column('spouse'),
            Column('spouse_date_of_birth')
        ),
        #Div(PrependedText('mobile_number', '+', active=True)),
        Div('mobile_number'),
        Row(
            Column('physical_address'),
            Column('emergency_information'),
        ),
        Row(
            Column('payment_method'),
            Column('payer_name'),
            Column('payment_account'),
        ),
        'comment',
        'status'
    )

    @property
    def full_name(self):
        return f"{self.registration_number} / {self.last_name} {self.middle_name}, {self.first_name}"
    
    @property
    def short_name(self):
        return f"{self.registration_number} / {self.last_name}"

    @property
    def name(self):
        return self.short_name
    
    def get_absolute_url(self):
        return reverse_lazy("employee:change", kwargs={"pk": self.pk})

    class Meta:
        abstract = True
        verbose_name = _('employé')
        verbose_name_plural = _('employés')