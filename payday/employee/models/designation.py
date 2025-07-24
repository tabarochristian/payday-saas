from django.utils.translation import gettext as _
from crispy_forms.layout import Layout
from core.models import Base, fields

class Designation(Base):
    group = fields.CharField(verbose_name=_('groupe'), max_length=100, blank=True, null=True, default=None)
    working_days_per_month = fields.IntegerField(verbose_name=_('jours ouvrables par mois'), default=22)
    name = fields.CharField(verbose_name=_('nom'), max_length=100, unique=True)

    layout = Layout('group', 'name', 'working_days_per_month', '_metadata')
    list_display = ('id', 'group', 'name', 'working_days_per_month')
    list_filter = ('working_days_per_month', 'group')
    

    def save(self, *args, **kwargs):
        self.group = self.group.upper() if self.group else self.group
        self.name = self.name.upper() if self.name else self.name
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _('position')
        verbose_name_plural = _('positions')
        
    def __str__(self):
        return self.name
