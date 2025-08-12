import logging
from django.db import models
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model

from django.contrib.contenttypes.fields import GenericForeignKey
from crispy_forms.layout import Layout, Column, Row
from core.models import fields, Base

logger = logging.getLogger(__name__)


class Approval(Base):
    """
    Generic approval model for workflow-based validation of any object.
    """

    workflow = fields.ModelSelectField(
        "core.workflow",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("workflow")
    )

    user = fields.ModelSelectField(
        get_user_model(),
        on_delete=models.PROTECT,
        verbose_name=_("approver")
    )

    content_type = fields.ModelSelectField(
        "contenttypes.contenttype",
        on_delete=models.CASCADE,
        verbose_name=_("model")
    )

    object_id = models.PositiveIntegerField(
        verbose_name=_("object ID")
    )

    content_object = GenericForeignKey("content_type", "object_id")

    comment = fields.TextField(
        null=True,
        blank=True,
        default=None,
        verbose_name=_("comment")
    )

    layout = Layout(
        "workflow",
        Row(Column("content_type"), Column("object_id")),
        "user",
        "status",
        "comment"
    )

    list_display = ("id", "workflow", "content_object", "object_id", "status", "updated_at")

    class Meta:
        verbose_name = _("approbation")
        verbose_name_plural = _("approbations")
        unique_together = ("user", "status", "content_type", "object_id")

    @property
    def is_approved(self) -> bool:
        """Returns True if this approval is marked as approved."""
        return self.status == "APPROVED"

    def get_absolute_url(self) -> str:
        """Returns the URL to edit the related object."""
        return reverse_lazy("core:change", kwargs={
            "model": self.content_type.model,
            "app": self.content_type.app_label,
            "pk": self.object_id
        })

    @staticmethod
    def get_action_required(user=None) -> list[dict]:
        """
        Returns a list of pending approvals, optionally filtered by user.
        Each item includes metadata for display or routing.
        """
        qs = Approval.objects.filter(status="PENDING")

        if user and callable(getattr(qs, "for_user", None)):
            qs = qs.for_user(user=user)

        return list(
            qs.select_related("content_type")
            .annotate(
                app=models.F("content_type__app_label"),
                model=models.F("content_type__model"),
                pk=models.F("object_id"),
                title=models.functions.Concat(
                    models.functions.Upper(models.F("content_type__model")),
                    models.Value(" n°"),
                    models.F("object_id"),
                    output_field=models.CharField()
                ),
                description=models.functions.Concat(
                    models.Value("Approbation requise pour "),
                    models.F("content_type__model"),
                    models.Value(" (ID "),
                    models.F("object_id"),
                    models.Value(")"),
                    output_field=models.TextField()
                ),
            )
            .values("app", "model", "title", "description", "pk")
            .distinct()
        )

    def save(self, *args, **kwargs) -> None:
        """
        Saves the approval and updates the related object's status
        if all approvals are marked as approved.
        """
        super().save(*args, **kwargs)

        outstanding = Approval.objects.filter(
            content_type=self.content_type,
            object_id=self.object_id
        ).exclude(status="APPROVED")

        if outstanding.exists():
            return

        try:
            obj = self.content_object
            if hasattr(obj, "status"):
                obj.status = "APPROVED"
                obj.save(update_fields=["status"])
        except Exception as e:
            logger.error("Unable to update related object status: %s", e)
