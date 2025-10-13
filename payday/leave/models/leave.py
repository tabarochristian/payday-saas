from datetime import timedelta
from django.utils.translation import gettext_lazy as _
from crispy_forms.layout import Layout, Column, Row
from core.models import Base, fields
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.timezone import now
from django.db.models import F, ExpressionWrapper, DurationField


class Status(models.TextChoices):
    PENDING = "PENDING", _("EN ATTENTE")
    APPROVED = "APPROVED", _("APPROUVÉ")
    REJECTED = "REJECTED", _("REJETÉ")


class Leave(Base):
    employee = fields.ModelSelectField(
        "employee.employee",
        on_delete=models.PROTECT,
        verbose_name=_("employé")
    )

    type_of_leave = fields.ModelSelectField(
        "leave.typeofleave",
        on_delete=models.CASCADE,
        verbose_name=_("type de congé")
    )

    reason = fields.TextField(
        blank=True,
        verbose_name=_("motif")
    )

    start_date = fields.DateField(verbose_name=_("date de début"))
    end_date = fields.DateField(verbose_name=_("date de fin"))

    status = fields.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_("statut"),
        editable=False
    )

    list_display = ('id', 'employee', 'type_of_leave',
                    'start_date', 'end_date', 'status')
    layout = Layout(
        'employee',
        'type_of_leave',
        Row(
            Column('start_date'),
            Column('end_date')
        ),
        'reason'
    )

    class Meta:
        verbose_name_plural = _("congés")
        verbose_name = _("congé")

    @property
    def name(self):
        return f"{self.employee} - {self.start_date}/{self.end_date} ({self.status})"

    @property
    def duration(self):
        """Calculates the leave duration"""
        return (self.end_date - self.start_date).days

    def clean(self):
        """Validation for leave duration, employee eligibility, max usage, and future date restriction"""

        if self.start_date >= self.end_date:
            raise ValidationError(
                _("la date de début doit être antérieure à la date de fin."))

        if self.start_date < now().date():
            raise ValidationError(
                _("vous ne pouvez pas demander un congé pour une date passée."))

        if self.type_of_leave.min_duration and self.duration < self.type_of_leave.min_duration:
            raise ValidationError(_("la durée minimale du congé est de {} jours.").format(
                self.type_of_leave.min_duration))

        # # Calculate total approved leave taken by the employee for this leave type
        # total_taken_leave = Leave.objects.filter(
        #     type_of_leave=self.type_of_leave,
        #     employee=self.employee,
        #     status=Status.APPROVED
        # ).aggregate(
        #     taken=models.Sum(
        #         ExpressionWrapper(F("end_date") - F("start_date"), output_field=DurationField())
        #     )
        # ).get("taken", timedelta(days=0)).days

        taken = Leave.objects.filter(
            type_of_leave=self.type_of_leave,
            employee=self.employee,
            status=Status.APPROVED
        ).aggregate(
            taken=models.Sum(
                ExpressionWrapper(F("end_date") - F("start_date"),
                                  output_field=DurationField())
            )
        )["taken"]

        total_taken_leave = taken.days if taken else 0

        if self.type_of_leave.max_duration and (total_taken_leave + self.duration) > self.type_of_leave.max_duration:
            raise ValidationError(_("vous avez atteint la limite maximale de congé ({}) pour ce type.").format(
                self.type_of_leave.max_duration))

        if self.type_of_leave.eligibility_after_days:
            days_since_joining = (
                self.start_date - self.employee.date_of_join).days
            if days_since_joining < self.type_of_leave.eligibility_after_days:
                raise ValidationError(_("vous devez attendre {} jours après votre embauche pour demander ce type de congé.").format(
                    self.type_of_leave.eligibility_after_days))
