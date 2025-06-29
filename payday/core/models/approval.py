from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
from crispy_forms.layout import Layout, Column, Row
from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from core.models import fields, Base
from django.urls import reverse_lazy
from core.models import fields
from django.db import models
import logging, re

logger = logging.getLogger(__name__)

class Status(models.TextChoices):
    PENDING = "PENDING", _("EN ATTENTE")
    APPROVED = "APPROVED", _("APPROUVÉ")
    REJECTED = "REJECTED", _("REJETÉ")

class ApprovalQuerySet(QuerySet):
    def __getattr__(self, attr):
        pattern = (
            r"get(?:_status_(?P<status>\w+))?"
            r"(?:_content_type_(?P<app_label>[a-z0-9_]+)_(?P<model>[a-z0-9_]+))?$"
        )
        match = re.match(pattern, attr)
        if not match:
            raise AttributeError(f"{self.__class__.__name__} has no attribute {attr}")

        status = match.group("status")
        app_label = match.group("app_label")
        model = match.group("model")

        def dynamic_method():
            qs = self
            if status:
                qs = qs.filter(status=status)
            if app_label and model:
                try:
                    ct = ContentType.objects.get(app_label=app_label, model=model)
                    qs = qs.filter(content_type=ct)
                except ContentType.DoesNotExist:
                    return self.none()
            return qs

        return dynamic_method

class ApprovalManager(models.Manager):
    def get_queryset(self):
        return ApprovalQuerySet(self.model, using=self._db)

class Approval(Base):
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

    content_object = GenericForeignKey(
        "content_type", 
        "object_id"
    )

    status = fields.CharField(
        max_length=10,
        choices=Status,
        default=Status.PENDING,
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
        Row(Column('content_type'), Column('object_id')),
        'user',
        'status',
        'comment'
    )

    list_display = ('id', 'workflow', 'content_object', 'object_id', 'status', 'updated_at')
    objects = ApprovalManager()

    @property
    def is_approved(self):
        return self.status in {"approved"}

    def get_absolute_url(self):
        return reverse_lazy("core:change", kwargs={
            "model": self.content_type.model,
            "app": self.content_type.app_label,
            "pk": self.object_id
        })
    
    @staticmethod
    def get_action_required(user=None):
        qs = Approval.objects.filter(status=Status.PENDING)

        # Safely apply custom user filter if available
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



    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Fetch all remaining approvals for this object that aren't "approved"
        outstanding = Approval.objects.filter(
            content_type=self.content_type,
            object_id=self.object_id
        ).exclude(
            status="APPROVED"
        )

        if outstanding.exists():
            return

        try:
            # If all are approved, update the related object's status
            status = "APPROVED"
            obj = self.content_object
            print(obj, status)
            if hasattr(obj, "status"):
                obj.status = status
                obj.save(update_fields=["status"])
        except Exception as e:
            logger.error("Can't update the status: %s", e)

    class Meta:
        verbose_name = _("approbation")
        verbose_name_plural = _("approbations")
        unique_together = ('user', 'status', 'content_type', 'object_id')
