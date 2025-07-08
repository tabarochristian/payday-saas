from datetime import time
from django.db.models import Q
from core.models.managers import PaydayQuerySet, PaydayManager
from core.models import Preference  # Prefer static import when possible

class AttendanceQuerySet(PaydayQuerySet):
    def _get_time_range(self, key: str, fallback: str) -> tuple[time, time]:
        try:
            range_str = Preference.get(key, fallback)
            start_str, end_str = map(str.strip, range_str.split('-'))
            start = time.fromisoformat(start_str)
            end = time.fromisoformat(end_str)
            return (start, end)
        except Exception as e:
            return {
                "DEFAULT_CHECK_OUT_RANGE:LIST": (time(16, 30), time(18, 30)),
                "DEFAULT_CHECK_IN_RANGE:LIST": (time(6, 0), time(8, 30))
            }.get(key)

    def check_in_range_time(self):
        return self._get_time_range('DEFAULT_CHECK_IN_RANGE:LIST', '06:00-08:30')

    def check_out_range_time(self):
        return self._get_time_range('DEFAULT_CHECK_OUT_RANGE:LIST', '16:30-18:30')

    def attended(self):
        check_out_range = self.check_out_range_time()
        check_in_range = self.check_in_range_time()

        return self.filter(
            Q(first_checked_at__time__range=check_in_range) &
            Q(last_checked_at__time__range=check_out_range)
        )

class AttendanceManager(PaydayManager):
    def get_queryset(self):
        return AttendanceQuerySet(self.model, using=self._db)
