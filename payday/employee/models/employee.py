from employee.models.base import Employee as BaseEmployee
from crispy_forms.layout import Layout, Row, Column, Div

from django.utils.translation import gettext as _
from crispy_forms.bootstrap import PrependedText
from core.utils import upload_directory_file
from django.urls import reverse_lazy

from core.models import fields
from django.db import models
from django.apps import apps

import random

def default_registration_number():
    while True:
        unique_int = random.randint(100000, 999999)  # Example: 6-digit number
        if not Employee.objects.filter(registration_number=unique_int).exists():
            return str(unique_int)

class Employee(BaseEmployee):
    create_user_on_save = fields.BooleanField(
        _('créer un utilisateur'),
        default=False,
        help_text=_('Créez un utilisateur pour cet employé si l\'adresse e-mail est fournie.')
    )

    user = fields.OneToOneField(
        'core.user', 
        verbose_name=_('utilisateur'), 
        blank=True, 
        null=True, 
        on_delete=models.SET_NULL, 
        default=None, 
        editable=False
    )

    photo = fields.ImageField(
        _('photo'), 
        upload_to=upload_directory_file, 
        blank=True, 
        null=True
    )

    devices = fields.ModelSelect2Multiple(
        'device.device',
        verbose_name=_('terminaux'),
        help_text=_('Veuillez choisir les terminaux de présence que l\'agent utilisera pour pointer.'),
        blank=True
    )

    registration_number = fields.CharField(
        _('matricule'), 
        max_length=50, 
        primary_key=True, 
        unique=True, 
        default=default_registration_number
    )

    email = fields.EmailField(
        _('email'), 
        blank=True, 
        null=True, 
        default=None
    )

    list_display = ('registration_number', 'last_name', 'middle_name', 'branch', 'designation', 'grade', 'status')
    inlines = ['employee.education', 'employee.child', 'payroll.specialemployeeitem']

    layout = Layout(
        Div(
            'photo',
        ),
        Div(
            Row(
                Column('registration_number'),
                Column('social_security_number')
            ),
            Row(
                Column('agreement', css_class="col-md-4"),
                Column('date_of_join', css_class="col-md-4"),
                Column('date_of_end', css_class="col-md-4"),
            ),
            Row(
                Column('direction', css_class="col-md-4"),
                Column('sub_direction', css_class="col-md-4"),
                Column('service', css_class="col-md-4"),
            ),
            Row(
                Column('branch', css_class="col-md-4"),
                Column('grade', css_class="col-md-4"),
                Column('designation', css_class="col-md-4"),
            ),
            Row(
                Column('payment_method', css_class="col-md-4"),
                Column('payer_name', css_class="col-md-4"),
                Column('payment_account', css_class="col-md-4"),
            ),
            css_class='bg-dark p-4 rounded mb-4'
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
        Div(
            Row(
                Column('marital_status'),
                Column('spouse'),
                Column('spouse_date_of_birth')
            ),
            css_class='bg-light-warning p-4 mb-4 rounded'
        ),
        Row(
            Column(Div(PrependedText('mobile_number', '+', active=True))),
            Column('email'),
        ),
        Row(
            Column('physical_address'),
            Column('emergency_information'),
        ),
        'comment',
        Div(
            'status',
            'devices',
            'create_user_on_save',
            css_class='bg-dark p-4 rounded'
        )
    )

    def payslips(self):
        model = apps.get_model('payroll', 'payslip')
        return model.objects.filter(**{'employee__registration_number': self.registration_number})
    
    def attendances(self, period=None):
        return list()
    
    @property
    def get_action_buttons(self):
        return [{
            'url': reverse_lazy('core:list', kwargs={'app': 'payroll', 'model': 'payslip'}) + '?employee__registration_number=' + self.registration_number,
            'permission': 'payroll.view_payslip',
            'classes': 'btn btn-light-info',
            'text': _('bulletins de paie').title(),
            'tag': 'a',
        }]
    
    def create_user(self):
        if not self.email: return
        if self.user: return self.user
        from django.contrib.auth import get_user_model
        
        user, created = get_user_model().objects.get_or_create(email=self.email)
        if created:
            from django.contrib.auth.models import Group
            from django.apps import apps
            
            preference = apps.get_model('core', 'preference')
            group = preference.get('DEFAULT_PERMISSION_GROUP')
            group = Group.objects.filter(name=group).first()
            if group: user.groups.add(group)

            password = preference.get('DEFAULT_USER_PASSWORD')
            if not password: 
                user.set_password(password)
                user.save()
                
        self.user = user
        self.save()

    class Meta:
        verbose_name = _('employé')
        verbose_name_plural = _('employés')
