from django.db import models
from django.apps import apps
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django.db.models.signals import post_save
from django.contrib.contenttypes.models import ContentType
from django_currentuser.db.models import CurrentUserField
from crispy_forms.layout import Layout

from api.serializers import model_serializer_factory
from core.models.managers import PaydayManager
from core.utils import DictToObject
from core.models import fields


def get_sub_organization_choices():
    try:
        SubOrg = apps.get_model('core', 'suborganization')
        names = SubOrg.objects.order_by().values_list('name', flat=True).distinct()
        return [(name, name) for name in names]
    except Exception:
        return []

class Status(models.TextChoices):
    PENDING = "PENDING", _("EN ATTENTE")
    APPROVED = "APPROVED", _("APPROUVÉ")
    REJECTED = "REJECTED", _("REJETÉ")

class Base(models.Model):
    _metadata = fields.JSONField(_("metadata"), default=dict, blank=True)

    sub_organization = fields.ChoiceField(
        _("sous-organization"),
        choices=get_sub_organization_choices,
        max_length=100,
        blank=True,
        null=True
    )

    status = fields.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_("statut"),
        editable=False
    )

    updated_by = CurrentUserField(
        _("mis à jour par"),
        related_name="%(app_label)s_%(class)s_updated_by",
        on_update=True,
        editable=False
    )

    created_by = CurrentUserField(
        _("créé par"),
        related_name="%(app_label)s_%(class)s_created_by",
        editable=False
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

    def __str__(self):
        return str(getattr(self, "name", super().__str__()))

    @property
    def metadata(self):
        return DictToObject(self._metadata)

    @property
    def serialized(self):
        serializer = model_serializer_factory(self.__class__)
        return serializer(self).data

    @property
    def get_action_buttons(self):
        return []
    
    @property
    def sub_organization_obj(self):
        if not self.sub_organization:
            return None
        model = apps.get_model('core', model_name='suborganization')
        return model.objects.filter(name=self.sub_organization).first()

    @staticmethod
    def get_action_required():
        return []

    @staticmethod
    def can_search():
        return True

    def get_absolute_url(self):
        return reverse_lazy(
            "core:change",
            args=[self._meta.app_label, self._meta.model_name, self.pk]
        )

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if not is_new:
            return

        Workflow = apps.get_model("core", "Workflow")
        Approval = apps.get_model("core", "Approval")

        content_type = ContentType.objects.get_for_model(self.__class__)
        workflows = Workflow.objects.filter(content_type=content_type).prefetch_related("users")

        if not workflows.exists() and hasattr(self, 'status'):
            self.status = Status.APPROVED
            super().save()
            return

        local_ctx = {"obj": self, "model": self._meta.model_name}
        valid_workflows = [
            wf for wf in workflows
            if not wf.condition or eval(wf.condition, {}, local_ctx)
        ]

        pending = Approval.objects.filter(
            content_type=content_type,
            object_id=self.pk,
            status="PENDING"
        ).values_list("user_id", "workflow_id")
        existing_keys = set(pending)

        approvals = [
            Approval(
                content_type=content_type,
                object_id=self.pk,
                status="PENDING",
                workflow=wf,
                user=user
            )
            for wf in valid_workflows
            for user in wf.users.all()
            if (user.pk, wf.pk) not in existing_keys
        ]
        if not approvals:
            return

        created = Approval.objects.bulk_create(approvals)
        [post_save.send(sender=Approval, instance=instance, created=True) for instance in created]
