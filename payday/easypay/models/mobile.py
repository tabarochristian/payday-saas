# payroll/models/mobile.py

from django.db import models
from django.utils.translation import gettext as _
from crispy_forms.layout import Layout
from core.models import Base, fields
from django.urls import reverse_lazy


class Mobile(Base):
    """
    A model to represent mobile money payment status for a given payroll.

    Tracks:
      - Which payroll is being processed
      - How many employees are involved
      - Payment status (e.g., PENDING, PROCESSING, COMPLETED)
      - Additional metadata (breakdown of amounts, logs, errors)
    """

    STATUS_CHOICES = (
        ("PENDING", _("En attente")),
        ("PROCESSING", _("En cours")),
        ("COMPLETED", _("Complété")),
        ("ERROR", _("Erreur")),
        ("CANCELLED", _("Annulé")),
    )

    payroll = fields.ModelSelectField(
        'payroll.Payroll',
        verbose_name=_('Paie'),
        blank=True,
        null=True,
        default=None,
        on_delete=models.SET_NULL
    )

    count = fields.IntegerField(
        verbose_name=_('Nombre de personnes à payer'),
        default=0
    )

    status = models.CharField(
        verbose_name=_("Statut"),
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
        db_index=True
    )

    executed_at = models.DateTimeField(
        verbose_name=_("Date d'exécution"),
        blank=True,
        null=True
    )

    amount_total = fields.FloatField(
        verbose_name=_("Montant total"),
        default=0
    )

    amount_paid = fields.FloatField(
        verbose_name=_("Montant payé"),
        default=0
    )

    # Crispy Form Layout
    list_display = ('id', 'payroll', 'count', 'status', 'amount_total', 'executed_at')
    layout = Layout('payroll', 'count', 'amount_total')
    list_filter = ('status', 'payroll')

    def name(self):
        return f"{self.payroll} - {self.get_status_display()}"

    def get_absolute_url(self):
        return reverse_lazy("payroll:payslips", kwargs={"pk": self.payroll.pk}) + '?payment_method=MOBILE MONEY'
    

    class Meta:
        verbose_name = _('mobile money')
        verbose_name_plural = _('mobile moneys')