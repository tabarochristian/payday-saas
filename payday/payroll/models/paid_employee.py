from django.utils.translation import gettext as _
from employee.models.base import Employee
from django.urls import reverse_lazy
from core.models import fields
from django.db import models


class PaidEmployee(Employee):
    payroll = fields.ModelSelectField(
        'payroll.payroll', 
        verbose_name=_('paie'), 
        blank=True, 
        null=True, 
        default=None, 
        on_delete=models.CASCADE
    )
    employee = fields.ModelSelectField(
        'employee.employee', 
        verbose_name=_('employé'), 
        blank=True, 
        null=True, 
        default=None, 
        on_delete=models.SET_NULL
    )

    attendance = fields.IntegerField(
        verbose_name=_('présence'), 
        default=0
    )

    registration_number = fields.CharField(verbose_name=_('matricule'), blank=True, null=True, default=None, max_length=255)
    agreement = fields.CharField(verbose_name=_('type de contrat'), blank=True, null=True, default=None, max_length=255)
    status = fields.CharField(verbose_name=_('statut'), blank=True, null=True, default=None, max_length=255)

    designation = fields.CharField(verbose_name=_('désignation'), blank=True, null=True, default=None, max_length=255)
    branch = fields.CharField(verbose_name=_('site'), blank=True, null=True, default=None, max_length=255)
    grade = fields.CharField(verbose_name=_('grade'), blank=True, null=True, default=None, max_length=255)

    subdirection = fields.CharField(verbose_name=_('sous-direction'), blank=True, null=True, default=None, max_length=255)
    direction = fields.CharField(verbose_name=_('direction'), blank=True, null=True, default=None, max_length=255)
    service = fields.CharField(verbose_name=_('service'), blank=True, null=True, default=None, max_length=255)

    working_days_per_month = fields.IntegerField(verbose_name=_('jours ouvrables par mois'), default=23)
    children = fields.IntegerField(verbose_name=_('children'), default=0)

    social_security_threshold = fields.FloatField(_('plafond cnss/cnsap'), default=0)
    taxable_gross = fields.FloatField(_('brut imposable'), default=0)
    
    gross = fields.FloatField(_('brut'), default=0)
    net = fields.FloatField(_('net'), default=0)

    @property
    def name(self):
        return self.short_name
    
    def get_absolute_url(self):
        return reverse_lazy("payroll:payslip", kwargs={"pk": self.id})

    def update(self):
        items = self.itempaid_set.filter(is_payable=True).order_by('code')
        self.gross = items.aggregate(models.Sum('amount_qp_employee'))
        self.gross = self.gross['amount_qp_employee__sum'] or 0

        self.net = items.aggregate(models.Sum('amount_qp_employee'))
        self.net = self.net['amount_qp_employee__sum'] or 0

        self.social_security_threshold = items.aggregate(models.Sum('social_security_amount'))
        self.social_security_threshold = self.social_security_threshold['social_security_amount__sum'] or 0

        self.taxable_gross = items.aggregate(models.Sum('taxable_amount'))
        self.taxable_gross = self.taxable_gross['taxable_amount__sum'] or 0

        self.save()

    class Meta:
        verbose_name = _('employé rémunéré')
        verbose_name_plural = _('employés rémunéré')
        ordering = ('-status', 'registration_number')