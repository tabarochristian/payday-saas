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
        on_delete=models.SET_NULL
    )

    attendance = fields.IntegerField(
        verbose_name=_('présence'), 
        default=0
    )

    registration_number = fields.CharField(verbose_name=_('matricule'), blank=True, null=True, default=None)
    agreement = fields.CharField(verbose_name=_('type de contrat'), blank=True, null=True, default=None)
    status = fields.CharField(verbose_name=_('statut'), blank=True, null=True, default=None)

    designation = fields.CharField(verbose_name=_('désignation'), blank=True, null=True, default=None)
    branch = fields.CharField(verbose_name=_('site'), blank=True, null=True, default=None)
    grade = fields.CharField(verbose_name=_('grade'), blank=True, null=True, default=None)

    subdirection = fields.CharField(verbose_name=_('sous-direction'), blank=True, null=True, default=None)
    direction = fields.CharField(verbose_name=_('direction'), blank=True, null=True, default=None)
    service = fields.CharField(verbose_name=_('service'), blank=True, null=True, default=None)

    @property
    def name(self):
        return self.short_name()
    
    def get_absolute_url(self):
        return reverse_lazy("employee:change", kwargs={"pk": self.registration_number})

    class Meta:
        verbose_name = _('employé rémunéré')
        verbose_name_plural = _('employés rémunéré')
        ordering = ('-status', 'registration_number')