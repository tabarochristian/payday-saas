from django.db import models
from core.models import Base, fields
from django.utils.timezone import now
from django.core.exceptions import ValidationError
from crispy_forms.layout import Layout, Column, Row
from django.utils.translation import gettext_lazy as _

class Status(models.TextChoices):
    PENDING = "PENDING", _("EN ATTENTE")
    APPROVED = "APPROVED", _("APPROUVÉ")
    REJECTED = "REJECTED", _("REJETÉ")

class EarlyLeave(Base):
    employee = fields.ModelSelectField(
        "employee.employee",
        on_delete=models.PROTECT,
        verbose_name=_("employé")
    )

    date = fields.DateField(
        default=now,
        verbose_name=_("date du départ anticipé")
    )
    
    start_time = fields.TimeField(verbose_name=_("heure de début"))
    end_time = fields.TimeField(verbose_name=_("heure de fin"))

    reason = fields.TextField(blank=True, verbose_name=_("motif"))

    status = fields.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_("statut"),
        editable=False
    )

    list_display = ('id', 'employee', 'date', 'start_time', 'end_time', 'status')
    layout = Layout(
        'employee',
        'date',
        Row(
            Column('start_time'),
            Column('end_time')
        ),
        'reason'
    )

    class Meta:
        verbose_name = _("départ anticipé")
        verbose_name_plural = _("départs anticipés")

    @property
    def name(self):
        return f"{self.employee} - {self.date} ({self.status})"

    def duration(self):
        """Calculates the duration of early leave in hours"""
        return (self.end_time.hour + self.end_time.minute / 60) - (self.start_time.hour + self.start_time.minute / 60)

    def clean(self):
        """Validation to ensure request date is today or later"""
        if self.date < now().date():
            raise ValidationError(_("vous ne pouvez pas demander un départ anticipé pour une date passée."))

        if self.start_time >= self.end_time:
            raise ValidationError(_("l'heure de début doit être antérieure à l'heure de fin."))
