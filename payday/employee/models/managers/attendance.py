from core.models.managers import CustomManager
from django.utils.dateparse import parse_date
from django.db.models import Q
from django.db import models

class AttendanceManager(models.Manager):
    def attended(self, min_attendance=1, *args, **kwargs):
        qs = self.get_queryset().filter(**kwargs)
        return qs.values('employee', 'checked_at__date') \
            .annotate(attended=models.Count('id')) \
                .filter(attended__gt=min_attendance)