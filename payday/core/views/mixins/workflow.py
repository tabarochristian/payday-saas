from typing import Optional
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from core.models import Workflow, Approval


class WorkflowMixin:
    ALLOWED_APPS = {'employee', 'leave', 'payroll'}

    _content_type_cache: Optional[ContentType] = None
    _approvals_cache: Optional[QuerySet] = None
    _object_cache: Optional[object] = None

    def get_model(self):
        """
        Must be implemented in subclass.
        Return the model class related to the workflow.
        """
        raise NotImplementedError("Implement get_model() returning the model class")

    def _model_allowed(self, model=None) -> bool:
        """
        Check if the model's app_label is in the allowed apps.
        If model not provided, use get_model().
        """
        if model is None:
            model = self.get_model()
        return model._meta.app_label in self.ALLOWED_APPS

    @property
    def content_type(self) -> Optional[ContentType]:
        if self._content_type_cache is not None:
            return self._content_type_cache

        model = self.get_model()
        if not self._model_allowed(model):
            return None

        self._content_type_cache = ContentType.objects.get_for_model(model, for_concrete_model=False)
        return self._content_type_cache

    def get_workflow_users_for_model(self) -> QuerySet:
        if not self._model_allowed():
            return get_user_model().objects.none()

        content_type = self.content_type
        if content_type is None:
            return get_user_model().objects.none()

        workflows = Workflow.objects.filter(content_type=content_type).prefetch_related('users')

        user_pks = set()
        obj = self._get_object() or None
        for wf in workflows:
            condition = eval(wf.condition, {
                **locals(),
                **{'obj':obj}
            })
            if not condition: continue
            user_pks.update(wf.users.values_list('pk', flat=True))

        return get_user_model().objects.filter(pk__in=user_pks).distinct()

    @property
    def approvals(self) -> QuerySet:
        obj = self._get_object()
        if obj is None or not self._model_allowed(type(obj)):
            return Approval.objects.none()

        content_type = ContentType.objects.get_for_model(obj, for_concrete_model=False)
        return Approval.objects.filter(
            content_type=content_type,
            object_id=obj.pk
        ).select_related('user')

    @property
    def approval(self) -> Optional[Approval]:
        if not hasattr(self, 'request') or not hasattr(self.request, 'user'):
            return None

        return self.approvals.filter(user=self.request.user).first()

    @property
    def approval_users(self) -> QuerySet:
        if not self._model_allowed():
            return get_user_model().objects.none()

        user_pks = self.approvals.values_list('user_id', flat=True).distinct()
        User = get_user_model()
        return User.objects.filter(pk__in=user_pks)

    @property
    def user_can_approve(self) -> bool:
        obj = self._get_object()
        if obj is None or not hasattr(obj, 'created_by') or not self._model_allowed(type(obj)):
            return False

        user = getattr(self.request, 'user', None)
        if user is None or user == obj.created_by:
            return False

        user_approval = self.approval
        if user_approval is None:
            return False

        if user_approval.status in {'approved', 'rejected'}:
            return False

        return user_approval
