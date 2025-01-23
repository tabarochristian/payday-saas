from core.models.managers import CustomManager, CustomQuerySet
from django.utils.dateparse import parse_date
from django.db.models import Q
from django.db import models

class AttendanceQuerySet(CustomQuerySet):
    def attended(self, min_attendance=1, *args, **kwargs):
        return self.filter(**kwargs).values('employee', 'checked_at__date') \
            .annotate(attended=models.Count('id')) \
                .filter(attended__gt=min_attendance)

class AttendanceManager(CustomManager):
    def get_queryset(self):
        return AttendanceQuerySet(self.model, using=self._db)