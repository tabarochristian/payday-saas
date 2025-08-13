# payday/managers.py

from django.db import models
from django.contrib.auth import get_user_model
from django.db.models import ForeignObjectRel
from core.utils import get_rls_filters
from collections import deque
from functools import reduce
from operator import or_


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
        Traverses model relations level by level.
        Stops at the first level where one or more paths to User are found,
        and applies filter using all those paths.
        """
        if not user or not user.is_authenticated:
            return self.none()

        model = self.model
        user_model = get_user_model()
        visited = set()
        queue = deque()

        # Start with direct relations
        for field in model._meta.get_fields():
            if field.is_relation and not isinstance(field, ForeignObjectRel):
                queue.append((field.name, field.related_model))

        while queue:
            level_size = len(queue)
            valid_paths = []

            # Scan entire current level
            next_level = deque()
            for _ in range(level_size):
                path, related_model = queue.popleft()

                if path in visited:
                    continue
                visited.add(path)

                if related_model == user_model:
                    valid_paths.append(path)
                else:
                    # Queue next-level relations
                    for field in related_model._meta.get_fields():
                        if field.is_relation and not isinstance(field, ForeignObjectRel):
                            new_path = f"{path}__{field.name}"
                            next_level.append((new_path, field.related_model))

            if valid_paths:
                # Stop here and apply filter using all valid paths
                filters = [models.Q(**{p: user}) for p in valid_paths]
                combined_filter = reduce(or_, filters)
                return self.filter(combined_filter).distinct()

            # Move to next level
            queue = next_level

        # No path to User found
        return self.none()


class PaydayManager(models.Manager):
    def get_queryset(self):
        return PaydayQuerySet(self.model, using=self._db)

    def for_user(self, user=None):
        return self.get_queryset().for_user(user)