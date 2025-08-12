import logging
import pandas as pd
from django.db import models
from django.apps import apps
from django.urls import reverse_lazy
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _
from django.utils.functional import cached_property
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django_currentuser.db.models import CurrentUserField
from django.db.models.signals import post_save
from crispy_forms.layout import Layout
from core.models import fields
from core.models.managers import PaydayManager
from core.utils import DictToObject
from api.serializers import model_serializer_factory

logger = logging.getLogger(__name__)


def get_sub_organization_choices() -> list[tuple[str, str]]:
    """Return cached suborganization choices as list of tuples."""
    cache_key = "suborganization_choices"
    choices = cache.get(cache_key)
    if choices:
        return choices

    try:
        SubOrg = apps.get_model("core", "SubOrganization")
        names = SubOrg.objects.order_by("name").values_list("name", flat=True).distinct()
        choices = [(name, name) for name in names]
        cache.set(cache_key, choices, 3600)
        return choices
    except LookupError:
        logger.warning("SubOrganization model not found")
        return []


class Status(models.TextChoices):
    PENDING = "PENDING", _("EN ATTENTE")
    APPROVED = "APPROVED", _("APPROUVÉ")
    REJECTED = "REJECTED", _("REJETÉ")


class Base(models.Model):
    """Abstract base model with common fields and workflow logic."""

    _metadata = fields.JSONField(_("metadata"), default=dict, blank=True)
    sub_organization = fields.ChoiceField(
        _("sous-organisation"),
        choices=get_sub_organization_choices,
        max_length=100,
        blank=True,
        null=True,
    )
    status = fields.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_("statut"),
    )
    updated_by = CurrentUserField(
        _("mis à jour par"),
        related_name="%(app_label)s_%(class)s_updated_by",
        on_update=True,
        editable=False,
    )
    created_by = CurrentUserField(
        _("créé par"),
        related_name="%(app_label)s_%(class)s_created_by",
        editable=False,
    )
    updated_at = fields.DateTimeField(_("mis à jour le/à"), auto_now=True, editable=False)
    created_at = fields.DateTimeField(_("créé le/à"), auto_now_add=True, editable=False)

    objects = PaydayManager()

    list_display = ("id", "name")
    search_fields = ("id",)
    list_filter = ()
    layout = Layout()

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return str(getattr(self, "name", f"{self.__class__.__name__} (id={self.pk})"))

    @property
    def metadata(self) -> DictToObject:
        return DictToObject(self._metadata)

    @property
    def serialized(self) -> dict:
        serializer = model_serializer_factory(self.__class__)
        return serializer(self).data

    @property
    def get_action_buttons(self) -> list:
        return []

    @cached_property
    def sub_organization_obj(self):
        if not self.sub_organization:
            return None
        SubOrg = apps.get_model("core", "SubOrganization")
        return SubOrg.objects.filter(name=self.sub_organization).first()

    @staticmethod
    def get_action_required() -> list:
        return []

    @staticmethod
    def can_search() -> bool:
        return True

    def get_absolute_url(self) -> str:
        return reverse_lazy("core:change", args=[self._meta.app_label, self._meta.model_name, self.pk])

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new:
            self._initialize_workflow_approvals()

    def approvals(self):
        Approval = apps.get_model("core", "Approval")
        content_type = ContentType.objects.get_for_model(self.__class__)
        return Approval.objects.filter(content_type=content_type, object_id=self.pk)

    def approvers(self):
        Workflow = apps.get_model("core", "Workflow")
        content_type = ContentType.objects.get_for_model(self.__class__)
        return Workflow.objects.filter(content_type=content_type).prefetch_related("users")

    def approvals_table(self) -> str:
        df = pd.DataFrame.from_records(
            self.approvals().values(
                "status", "user__email", "created_at", "updated_at", "comment"
            )
        )

        if df.empty:
            return ""

        for col in ("created_at", "updated_at"):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col]).dt.strftime("%Y-%m-%d %H:%M")

        df.sort_values(by=["updated_at", "status", "user__email"], ascending=[False, True, True], inplace=True)
        df.rename(columns={
            "status": "Statut",
            "user__email": "Acteur",
            "created_at": "Créé le/à",
            "updated_at": "Modifié le/à",
            "comment": "Commentaire",
        }, inplace=True)

        return df.to_html(classes="table table-bordered table-striped", index=False, escape=False)

    def _initialize_workflow_approvals(self):
        Workflow = apps.get_model("core", "workflow")
        Approval = apps.get_model("core", "approval")
        content_type = ContentType.objects.get_for_model(self.__class__)
        workflows = Workflow.objects.filter(content_type=content_type).prefetch_related("users")

        model_name = self.__class__.__name__.lower()
        if all([
            not workflows.exists(),
            hasattr(self, "status"),
            self.status != None,
            model_name != "payroll"
        ]):
            self.status = Status.APPROVED
            super().save(update_fields=["status"])
            return

        local_ctx = {
            "model": self._meta.model_name,
            "content_type": content_type, 
            "obj": self, 
        }
        valid_workflows = [
            wf for wf in workflows
            if not wf.condition or self._evaluate_condition(wf.condition, local_ctx)
        ]

        existing_keys = set(
            Approval.objects.filter(
                content_type=content_type, object_id=self.pk, status=Status.PENDING
            ).values_list("user_id", "workflow_id")
        )

        new_approvals = [
            Approval(
                sub_organization=self.sub_organization,
                content_type=content_type,
                status=Status.PENDING,
                object_id=self.pk,
                workflow=wf,
                user=user,
            )
            for wf in valid_workflows
            for user in wf.users.all()
            if (user.pk, wf.pk) not in existing_keys
        ]

        new_approvals = Approval.objects.bulk_create(new_approvals)
        for instance in new_approvals:
            post_save.send(sender=Approval, instance=instance, created=True)

    def _evaluate_condition(self, condition: str, context: dict) -> bool:
        """Safely evaluate a workflow condition string."""
        try:
            return bool(eval(condition, {}, context))
        except Exception as e:
            logger.warning(f"Échec de l'évaluation de la condition '{condition}': {e}")
            return False
