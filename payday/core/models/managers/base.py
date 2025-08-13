# payday/managers.py

from django.db import models
from django.contrib.auth import get_user_model
from core.utils import get_rls_filters
from functools import reduce
from operator import or_
from collections import deque
from django.db.models.fields.reverse_related import ForeignObjectRel

class PaydayQuerySet(models.QuerySet):
    def for_user(self, user=None):
        """
        Returns only the objects accessible by the given user.
        Combines:
            - User relation detection (direct or deeply nested)
            - Row-level security (RLS) filters
        """
        user = user or self._get_current_user()
        if not user or not user.is_authenticated:
            return self.none()

        if user.is_superuser or user.is_staff:
            return self.all()

        # Step 1: Apply automatic user-related field filtering (deep nesting support)
        qs = self._apply_user_relation_filter(user)

        # Step 2: Apply RLS-style dynamic filters if available
        rls_filters = get_rls_filters(user, self.model)
        if rls_filters:
            try:
                qs = qs.filter(**rls_filters)
            except Exception as e:
                # Optional: log warning here
                pass

        return qs.distinct()

    def _get_current_user(self):
        """
        Retrieve current user from middleware/context.
        Replace with your actual implementation.
        """
        try:
            from django_currentuser.middleware import get_current_user
            return get_current_user()
        except ImportError:
            return None

    def _apply_user_relation_filter(self, user):
        """
        Detect all paths (direct or deeply nested) that relate to the User model.
        Applies filter to only include records related to the given user.
        Works for any depth: level 1, 2, 3+, safely and efficiently.
        """
        if not user or not user.is_authenticated:
            return self.none()

        model = self.model
        valid_paths = []

        visited = set()
        queue = deque()

        # Start BFS from each direct relation of the current model
        for field in model._meta.get_fields():
            if field.is_relation and not isinstance(field, ForeignObjectRel):
                queue.append((field.name, field.related_model))

        while queue:
            path, related_model = queue.popleft()

            if path in visited:
                continue
            visited.add(path)

            if related_model == get_user_model():
                valid_paths.append(path)
                continue

            for field in related_model._meta.get_fields():
                if field.is_relation and not isinstance(field, ForeignObjectRel):
                    new_path = f"{path}__{field.name}"
                    queue.append((new_path, field.related_model))

        if not valid_paths:
            return self.none()

        # Build ORed Q objects: user is in any of these paths
        filters = [models.Q(**{f"{p}": user}) for p in valid_paths]
        combined_filter = reduce(or_, filters)

        return self.filter(combined_filter).distinct()


class PaydayManager(models.Manager):
    def get_queryset(self):
        return PaydayQuerySet(self.model, using=self._db)

    def for_user(self, user=None):
        return self.get_queryset().for_user(user)