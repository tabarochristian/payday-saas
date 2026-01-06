from employee.models.base import Employee as BaseEmployee
from crispy_forms.layout import Layout, Row, Column, Div

from django.utils.translation import gettext as _
from crispy_forms.bootstrap import PrependedText
from core.utils import upload_directory_file
from django.urls import reverse_lazy

from core.models import fields
from django.db import models
from django.apps import apps

import random, logging

logger = logging.getLogger(__name__)

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
        help_text=_("Photo passport de format standard, MAX 1MB"),
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
        default=default_registration_number
    )

    email = fields.EmailField(
        _('email'), 
        blank=True, 
        null=True, 
        default=None
    )

    list_display = ('registration_number', 'last_name', 'middle_name', 'branch', 'designation', 'grade', 'status')
    inlines = ['employee.document', 'employee.education', 'employee.child', 'payroll.specialemployeeitem']

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
                Column('subdirection', css_class="col-md-4"),
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
        ),
        '_metadata'
    )

    def payslips(self):
        model = apps.get_model('payroll', 'paidemployee')
        return model.objects.filter(**{'employee__registration_number': self.registration_number})
    
    def attendances(self, filter = {}):
        attendance = apps.get_model('employee', 'attendance')
        return attendance.objects.filter(employee=self).filter(**filter)

    def advance_salary(self, period):
        AdvanceSalaryPayment = apps.get_model('payroll', 'AdvanceSalaryPayment')

        queryset = AdvanceSalaryPayment.objects.filter(
            advance_salary__employee=self
        )

        if period:
            queryset = queryset.filter(
                date__year=period.year,
                date__month=period.month
            )

        return queryset
    
    @property
    def get_action_buttons(self):
        return [{
            'url': reverse_lazy('core:list', kwargs={'app': 'payroll', 'model': 'paidemployee'}) + f'?employee__registration_number={self.registration_number}',
            'permission': 'payroll.view_paidemployee',
            'text': _('bulletins de paie').title(),
            'classes': 'btn btn-light-info',
            'tag': 'a',
        }]


    def web_attendance(self):
        return self.devices.all().filter(
            geofence_center__isnull=False,
            geofence_radius__isnull=False
        )

    def device_attendance(self):
        return self.devices.all().filter(
            geofence_center__isnull=False,
            geofence_radius__isnull=False
        )
    
    def create_user(self):
        if not self.email:
            return

        if self.user:
            return self.user

        from django.contrib.auth import get_user_model
        from django.apps import apps

        UserModel = get_user_model()
        user, created = UserModel.objects.get_or_create(email=self.email)

        if not created:
            return user  # return existing user safely

        Preference = apps.get_model('core', 'preference')
        Group = apps.get_model('core', 'group')

        # Assign group if available
        group_name = Preference.get('DEFAULT_USER_ROLE:STR')
        groups = Group.objects.filter(name=group_name)

        if groups:
            user.groups.set(groups)
            group = groups.values_list('name', flat=True)
            group_names = ', '.join(user.groups.all().values_list('name', flat=True))
            logger.info(f"User '{user.email}' assigned to group '{group_name}'. Current groups: [{group_names}]")
        else:
            logger.warning(f"Default group '{group_name}' not found for user '{user.email}'")

        # Set password (defaults if missing)
        password = Preference.get('DEFAULT_USER_PASSWORD:STR', 'Kinshasa-2021')
        user.set_password(password)
        user.save()

        self.user = user
        self.save()

        logger.info(f"User instance linked and saved for email: {self.email}")
        return user


    class Meta:
        verbose_name = _('employé')
        verbose_name_plural = _('employés')
        unique_together = ["sub_organization", "registration_number"]
