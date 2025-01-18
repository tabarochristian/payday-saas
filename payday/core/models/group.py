from django.utils.translation import gettext_lazy as _
from crispy_forms.layout import Layout
from core.models import fields
from django.db import models

class Group(models.Model):
    """
    Groups are a generic way of categorizing users to apply permissions, or
    some other label, to those users. A user can belong to any number of
    groups.

    A user in a group automatically has all the permissions granted to that
    group. For example, if the group 'Site editors' has the permission
    can_edit_home_page, any user in that group will have that permission.

    Beyond permissions, groups are a convenient way to categorize users to
    apply some label, or extended functionality, to them. For example, you
    could create a group 'Special users', and you could write code that would
    do special things to those users -- such as giving them access to a
    members-only portion of your site, or sending them members-only email
    messages.
    """    

    name = fields.CharField(
        _("name"), 
        max_length=150, 
        unique=True
    )
    
    permissions = fields.ModelSelect2Multiple(
        "auth.permission",
        verbose_name=_("permissions"),
        blank=True,
        related_name="groups"
    )


    inlines = ('core.fieldpermission', 'core.rowlevelsecurity')
    layout = Layout('name', 'permissions')

    class Meta:
        verbose_name = _("group")
        verbose_name_plural = _("groups")

    def __str__(self):
        return self.name

    def natural_key(self):
        return (self.name,)