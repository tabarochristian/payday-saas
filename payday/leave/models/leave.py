from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils.timezone import now
from django.db.models import Sum, F, Q

from core.models import Base, fields
from crispy_forms.layout import Layout, Column, Row

class Status(models.TextChoices):
    PENDING = "PENDING", _("EN ATTENTE")
    APPROVED = "APPROVED", _("APPROUVÉ")
    REJECTED = "REJETÉ", _("REJETÉ")

class Leave(Base):
    """
    Optimized Leave model with integrated UI Layout and Business Logic.
    """
    employee = fields.ModelSelectField(
        "employee.employee",
        on_delete=models.PROTECT,
        verbose_name=_("employé")
    )
    type_of_leave = fields.ForeignKey(
        "leave.typeofleave",
        on_delete=models.CASCADE,
        verbose_name=_("type de congé")
    )
    
    start_date = fields.DateField(verbose_name=_("date de début"), db_index=True)
    end_date = fields.DateField(verbose_name=_("date de fin"), db_index=True)
    
    # Standard field updated in save() for high-speed indexing/aggregation
    duration = models.IntegerField(
        verbose_name=_("durée (jours)"),
        default=0,
        editable=False
    )
    
    status = fields.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_("statut"),
        editable=False,
        db_index=True,
    )
    
    reason = fields.TextField(blank=True, verbose_name=_("motif"))

    # --- UI & Admin Configuration ---
    list_display = (
        'id', 'employee', 'type_of_leave',
        'start_date', 'end_date', 'duration', 'status'
    )

    layout = Layout(
        'employee',
        'type_of_leave',
        Row(
            Column('start_date', css_class='form-group col-md-6 mb-0'),
            Column('end_date', css_class='form-group col-md-6 mb-0')
        ),
        'reason'
    )

    class Meta:
        verbose_name = _("congé")
        verbose_name_plural = _("congés")
        ordering = ('-start_date',)
        indexes = [
            models.Index(fields=['employee', 'type_of_leave', 'status']),
        ]
        # constraints = [
        #     models.CheckConstraint(
        #         check=Q(end_date__gte=F('start_date')),
        #         name='leave_valid_date_range',
        #     ),
        # ]

    def __str__(self):
        return f"{self.employee} - {self.start_date} → {self.end_date}"

    @property
    def name(self):
        return f"{self.employee} - {self.start_date}/{self.end_date} ({self.get_status_display()})"

    # --- Business Logic ---
    def calculate_duration(self) -> int:
        """Centralized calculation logic."""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days
        return 0

    def clean(self):
        super().clean()
        if not (self.start_date and self.end_date):
            return

        if self.start_date >= self.end_date:
            raise ValidationError({'end_date': _("La date de début doit être antérieure à la date de fin.")})

        # Logic for new requests
        if not self.pk and self.start_date < now().date():
            raise ValidationError({'start_date': _("Date passée non autorisée.")})

        current_duration = self.calculate_duration()

        # Balance/Eligibility Check (Optimized to use the 'duration' field)
        if self.type_of_leave and self.type_of_leave.max_duration:
            already_taken = Leave.objects.filter(
                employee=self.employee,
                type_of_leave=self.type_of_leave,
                status=Status.APPROVED
            ).exclude(pk=self.pk).aggregate(total=Sum('duration'))['total'] or 0

            if (already_taken + current_duration) > self.type_of_leave.max_duration:
                raise ValidationError(_("Limite de congé dépassée."))

    def save(self, *args, **kwargs):
        """
        Final check: ensures 'duration' is always calculated before the row is written.
        """
        self.duration = self.calculate_duration()
        super().save(*args, **kwargs)

    # --- Actions ---
    def approve(self):
        self.status = Status.APPROVED
        self.save(update_fields=['status'])

    def reject(self):
        self.status = Status.REJECTED
        self.save(update_fields=['status'])