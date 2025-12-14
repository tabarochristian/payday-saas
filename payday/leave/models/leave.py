from datetime import timedelta
from django.utils.translation import gettext_lazy as _
from crispy_forms.layout import Layout, Column, Row
from core.models import Base, fields
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.timezone import now

from django.db.models import F, ExpressionWrapper, DurationField, GeneratedField, IntegerField, Func
from django.db import connection


# ----------------------------------------------------------------------------------
# FIX FOR POSTGRESQL GENERATED FIELD ERROR (interval / interval)
# ----------------------------------------------------------------------------------

class Epoch(Func):
    """
    Custom Django function for PostgreSQL's EXTRACT(EPOCH FROM interval).
    This safely converts the date difference (interval) into total seconds (numeric).
    """
    function = 'EXTRACT'
    template = '%(function)s(EPOCH FROM %(expressions)s)'
    output_field = IntegerField()


def get_duration_expression():
    """
    Returns the appropriate ExpressionWrapper for the database in use.
    Uses Epoch/86400 for PostgreSQL and the simpler timedelta division for others (like SQLite).
    """
    if connection.vendor == 'postgresql':
        # PostgreSQL-safe calculation: (Total Seconds / Seconds in a day)
        return ExpressionWrapper(
            Epoch(F('end_date') - F('start_date')) / 86400,
            output_field=IntegerField()
        )
    else:
        # Standard calculation for SQLite, MySQL, etc.
        return ExpressionWrapper(
            (F('end_date') - F('start_date')) / timedelta(days=1),
            output_field=IntegerField()
        )

# ----------------------------------------------------------------------------------
# LEAVE MODEL
# ----------------------------------------------------------------------------------

class Status(models.TextChoices):
    PENDING = "PENDING", _("EN ATTENTE")
    APPROVED = "APPROVED", _("APPROUVÉ")
    REJECTED = "REJETÉ"


class Leave(Base):
    """
    Leave model with cross-database support for the GeneratedField 'duration'.
    """
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

    # The field 'duration' uses the database-aware expression helper.
    duration = GeneratedField(
        expression=get_duration_expression(),
        output_field=IntegerField(
            verbose_name=_("durée (jours)"),
            default=0,
            editable=False
        ),
        db_persist=True,
    )

    status = fields.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_("statut"),
        editable=False
    )

    list_display = ('id', 'employee', 'type_of_leave',
                    'start_date', 'end_date', 'duration', 'status')
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

    def get_calculated_duration(self):
        """
        Performs the Python calculation for duration, serving as the necessary
        fallback when reading the GeneratedField on an unsaved model instance (during clean()).
        """
        # If the object is saved (has a PK), we rely on the DB-calculated value (self.duration).
        # Otherwise, calculate it in Python for validation.
        if self.pk is not None and self.duration is not None and self.duration > 0:
            return self.duration
        
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days
        return 0

    def clean(self):
        """Validation for leave duration, employee eligibility, max usage, and future date restriction"""

        # 1. Date Validation
        if self.start_date and self.end_date:
            if self.start_date >= self.end_date:
                raise ValidationError(
                    _("la date de début doit être antérieure à la date de fin."))

        if self.start_date < now().date():
            raise ValidationError(
                _("vous ne pouvez pas demander un congé pour une date passée."))

        # Get the current duration, using the Python fallback if unsaved
        current_duration = self.get_calculated_duration()
        
        # 2. Minimum Duration Check
        if self.type_of_leave.min_duration and current_duration < self.type_of_leave.min_duration:
            raise ValidationError(_("la durée minimale du congé est de {} jours.").format(
                self.type_of_leave.min_duration))

        # 3. Maximum Duration Check (Requires aggregate calculation)
        
        # Exclude the current instance's duration from the 'taken' total for updates
        taken_queryset = Leave.objects.filter(
            type_of_leave=self.type_of_leave,
            employee=self.employee,
            status=Status.APPROVED
        )
        if self.pk:
             taken_queryset = taken_queryset.exclude(pk=self.pk)
             
        taken = taken_queryset.aggregate(
            taken=models.Sum(
                ExpressionWrapper(F("end_date") - F("start_date"),
                                  output_field=DurationField())
            )
        ).get("taken", 0)

        total_taken_leave = taken.days if taken else 0

        if self.type_of_leave.max_duration and (total_taken_leave + current_duration) > self.type_of_leave.max_duration:
            raise ValidationError(_("vous avez atteint la limite maximale de congé ({}) pour ce type.").format(
                self.type_of_leave.max_duration))

        # 4. Eligibility Check
        if self.type_of_leave.eligibility_after_days:
            days_since_joining = (
                self.start_date - self.employee.date_of_join).days
            if days_since_joining < self.type_of_leave.eligibility_after_days:
                raise ValidationError(_("vous devez attendre {} jours après votre embauche pour demander ce type de congé.").format(
                    self.type_of_leave.eligibility_after_days))
        
        super().clean()