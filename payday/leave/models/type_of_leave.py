from django.utils.translation import gettext_lazy as _
from crispy_forms.layout import Layout, Column, Row
from django.core.exceptions import ValidationError
from core.models import Base, fields

class TypeOfLeave(Base):
    name = fields.CharField(
        max_length=100, 
        verbose_name=_("type de congé")
    )

    description = fields.TextField(
        blank=True, 
        verbose_name=_("description")
    )

    min_duration = fields.PositiveIntegerField(
        default=1, 
        verbose_name=_("durée minimale (jours)")
    )

    max_duration = fields.PositiveIntegerField(
        default=30,  
        verbose_name=_("durée maximale (jours)")
    )

    eligibility_after_days = fields.PositiveIntegerField(
        default=30,  
        verbose_name=_("délai avant d'être éligible (jours)")
    )
    status = None

    list_display = ('id', 'name', 'min_duration', 'max_duration', 'eligibility_after_days', 'updated_at')
    layout = Layout(
        # 'sub_organization',
        'name',
        'description',
        Row(
            Column('min_duration'),
            Column('max_duration')
        ),
        'eligibility_after_days'
    )

    class Meta:
        verbose_name_plural = _("types de congé")
        verbose_name = _("type de congé")

    def clean(self):
        """ensures min_duration is not greater than max_duration"""
        if self.min_duration > self.max_duration:
            raise ValidationError(_("la durée minimale ne peut pas être supérieure à la durée maximale."))
