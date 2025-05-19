from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils.translation import gettext_lazy as _
from crispy_forms.layout import Layout, Column, Row
from core.models import fields


class Approval(models.Model):
    workflow = fields.ModelSelectField(
        "core.workflow",
        on_delete=models.SET_NULL,  # Prevent deletion of approval records
        null=True,
        blank=True,
        verbose_name=_("workflow")
    )
    user = fields.ModelSelectField(
        get_user_model(),
        on_delete=models.PROTECT,  # Ensure users linked to approvals cannot be deleted
        verbose_name=_("approver")
    )

    content_type = fields.ModelSelectField(
        "contenttypes.contenttype",
        on_delete=models.CASCADE,
        verbose_name=_("model")
    )
    object_id = fields.PositiveIntegerField(
        verbose_name=_("object id")
    )
    content_object = GenericForeignKey(
        "content_type", 
        "object_id"
    )

    status = fields.CharField(
        max_length=10,
        choices=[
            ("pending", _("Pending")),
            ("approved", _("Approved")),
            ("rejected", _("Rejected")),
        ],
        default="pending",
        verbose_name=_("status")
    )
    comment = fields.TextField(
        null=True,
        blank=True,
        verbose_name=_("comment"),
        default=None
    )

    layout = Layout(
        'workflow',
        Row(
            Column('content_type'),
            Column('object_id')
        ),
        'user',
        'status',
        'comment'
    )

    list_display = (
        'id', 
        'workflow', 
        'content_object', 
        'status', 
        'updated_at'
    )

    class Meta:
        verbose_name_plural = _("approvals")
        verbose_name = _("approval")
