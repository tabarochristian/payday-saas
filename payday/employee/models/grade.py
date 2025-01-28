from django.utils.translation import gettext as _
from crispy_forms.layout import Layout
from core.models import Base, fields

class Grade(Base):
    group = fields.CharField(verbose_name=_('groupe'), max_length=100, blank=True, null=True, default=None)
    name = fields.CharField(verbose_name=_('nom'), max_length=100, unique=True)

    layout = Layout('group', 'name', '_metadata')
    list_display = ('id', 'group', 'name')
    list_filter = ('group', )

    def save(self, *args, **kwargs):
        self.group = self.group.upper() if self.group else self.group
        self.name = self.name.upper() if self.name else self.name
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _('grade')
        verbose_name_plural = _('grades')
        
    def __str__(self):
        return self.name

"""
{
  "base": 100,
  "logement": 200,
  "energy": 50,
  "ind. vie chere": 150,
  "ind. kilometrique": 170
}
"""