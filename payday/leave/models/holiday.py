from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from datetime import timedelta
from core.models import Base, fields
from crispy_forms.layout import Layout, Column, Row

# ----------------------------------------------------------------------------------
# Holiday Model
# ----------------------------------------------------------------------------------

class Holiday(Base):
    """
    Represents a holiday period with working-day calculations handled in Python.
    Calculations are dynamic, fetching the work-week configuration.
    """

    name = fields.CharField(max_length=255, verbose_name=_("Nom du jour férié"))

    start_date = fields.DateField(verbose_name=_("Date de début"), db_index=True)
    end_date = fields.DateField(verbose_name=_("Date de fin"), db_index=True)

    is_recurring = models.BooleanField(
        default=False,
        verbose_name=_("Récurrent"),
        help_text=_("Si activé, ce jour férié se répète chaque année aux mêmes dates."),
    )

    description = fields.TextField(blank=True, null=True, verbose_name=_("Description"))
    
    days = models.IntegerField(
        verbose_name=_("Jours ouvrables"),
        editable=False,
        default=0,
    )

    # --- UI & Admin Configuration ---
    list_display = (
        'name', 'start_date', 'end_date', 'days', 'is_recurring'
    )
    
    list_filter = ('is_recurring', 'start_date')
    
    search_fields = ('name', 'description')

    layout = Layout(
        'name',
        Row(
            Column('start_date', css_class='form-group col-md-6 mb-0'),
            Column('end_date', css_class='form-group col-md-6 mb-0')
        ),
        'is_recurring',
        'description'
    )

    class Meta:
        verbose_name = _("Jour férié")
        verbose_name_plural = _("Jours fériés")
        ordering = ("-start_date",)
        constraints = (
            models.CheckConstraint(
                check=models.Q(end_date__gte=models.F("start_date")),
                name="holiday_valid_date_range",
            ),
        )
        indexes = (models.Index(fields=("start_date", "end_date")),)

    def __str__(self):
        return f"{self.name} ({self.start_date})"

    # --- Business Logic ---

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError({
                "end_date": _("La date de fin ne peut pas être antérieure à la date de début.")
            })

    def calculate_working_days(self):
        """
        Calculates working days using the configured work week.
        Stored in self.days on save to optimize filtering/summing.
        """
        from django.apps import apps
        
        if not self.start_date or not self.end_date:
            return 0

        # Fetch work week configuration
        try:
            Preference = apps.get_model('core', 'preference')
            default_config = getattr(settings, "WORKING_DAYS", "0,1,2,3,4")
            raw_work_days = Preference.get("WORKING_DAYS", default_config)
        except (LookupError, AttributeError):
            raw_work_days = "0,1,2,3,4"

        try:
            work_days_set = {
                int(d.strip()) 
                for d in str(raw_work_days).split(",") 
                if d.strip().isdigit()
            }
        except Exception:
            work_days_set = {0, 1, 2, 3, 4}

        count = 0
        current_date = self.start_date
        total_range = (self.end_date - self.start_date).days + 1
        
        for _ in range(total_range):
            if current_date.weekday() in work_days_set:
                count += 1
            current_date += timedelta(days=1)
            
        return count

    def save(self, *args, **kwargs):
        """
        Persist the working days count before database write.
        """
        self.days = self.calculate_working_days()
        super().save(*args, **kwargs)

    @property
    def duration_display(self):
        days = self.days
        return _("%(count)d jour%(plural)s") % {
            "count": days,
            "plural": "" if days <= 1 else "s",
        }