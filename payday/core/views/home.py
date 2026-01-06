from django.db.models import Count, Sum, Q, F, ExpressionWrapper, DurationField
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from django.utils import timezone
from django.apps import apps

from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from datetime import timedelta

class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Performance: Select related employee and user in one go
        employee = getattr(user, 'employee', None)
        sub_org = getattr(self.request, "suborganization", None)
        
        # 1. Fetch data efficiently
        data = {
            'employee': employee,
            'is_admin': user.is_staff or user.is_superuser,
            'attendance': self._get_today_attendance(employee),
            'leave_balances': self._get_optimized_leaves(employee),
            'admin_stats': self._get_admin_metrics(user, sub_org)
        }

        # 2. Build the flexible Widget Grid
        context['widgets'] = self._get_visible_widgets(data)
        return context

    def _get_today_attendance(self, employee):
        if not employee: return None
        Attendance = apps.get_model('employee', 'Attendance')
        return Attendance.objects.filter(
            employee=employee, 
            first_checked_at__date=timezone.localdate()
        ).first()

    def _get_optimized_leaves(self, employee):
        """Database-level calculation for all leave types at once."""
        if not employee: return []
        TypeOfLeave = apps.get_model('leave', 'TypeOfLeave')
        return TypeOfLeave.objects.annotate(
            used=Sum(
                ExpressionWrapper(
                    F('leave__end_date') - F('leave__start_date') + timedelta(days=1),
                    output_field=DurationField()
                ),
                filter=Q(
                    leave__employee=employee,
                    leave__start_date__year=timezone.now().year,
                    leave__status='APPROVED'
                )
            )
        ).values('name', 'max_duration', 'used')

    def _get_upcoming_holidays(self):
        # Assuming a 'core' or 'leave' app has a Holiday model
        Holiday = apps.get_model('leave', 'Holiday')
        return Holiday.objects.filter(
            date__gte=timezone.localdate()
        ).order_by('date')[:3]

    def _get_absent_today(self):
        Leave = apps.get_model('leave', 'Leave')
        return Leave.objects.filter(
            start_date__lte=timezone.localdate(),
            end_date__gte=timezone.localdate(),
            status='APPROVED'
        ).select_related('employee')[:6]

    def _get_celebrations(self):
        Employee = apps.get_model('employee', 'Employee')
        today = timezone.localdate()
        # Birthdays or Anniversaries this month
        return Employee.objects.filter(
            Q(date_of_birth__month=today.month) | Q(date_of_join__month=today.month)
        ).order_by('date_of_birth__day')[:5]

    def _get_pending_approvals(self, user):
        Leave = apps.get_model('leave', 'Leave')
        # Show only if user is a manager or admin
        return Leave.objects.filter(status='PENDING').select_related('employee')[:5]

    def _get_latest_notice(self):
        return {}

    def _get_admin_metrics(self, user, sub_org):
        if not (user.is_staff or user.is_superuser): return None
        Employee = apps.get_model('employee', 'Employee')
        qs = Employee.objects.for_user(user)
        if sub_org: qs = qs.filter(sub_organization=sub_org)
        return qs.values('status__name').annotate(count=Count('id'))

    def _get_visible_widgets(self, data):
        """
        The Layout Engine.
        This allows you to control the UI purely from Python.
        """
        user = self.request.user
        
        # Definition of all possible widgets
        all_widgets = [
            {
                "id": "attendance",
                "title": "Clock In/Out",
                "template": "widgets/home/attend.html",
                "ctx": {
                    'attendance': data['attendance']
                },
                "perm": "employee.view_attendance",
                "col": "col-lg-12",  # Full width top bar
                "visible": True if data['employee'] else False
            },
            {
                "id": "pending_approvals",
                "title": "Pending Requests",
                "template": "widgets/home/pending.html",
                "ctx": {
                    'pending_leaves': self._get_pending_approvals(user)
                },
                "perm": "leave.change_leave", 
                "col": "col-lg-8", # Main area for admins
                "visible": data['is_admin']
            },
            {
                "id": "admin_stats",
                "title": "Organization Health",
                "template": "widgets/home/stats.html",
                "ctx": {
                    'stats': data['admin_stats']
                },
                "perm": "employee.view_employee",
                "col": "col-lg-4", # Sidebar for admins
                "visible": data['is_admin']
            },
            {
                "id": "leaves",
                "title": "My Leave Balances",
                "template": "widgets/home/leaves.html",
                "ctx": {
                    'leaves': data['leave_balances']
                },
                "perm": "leave.view_leave",
                "col": "col-lg-4",
                "visible": True if data['employee'] else False
            },
            {
                "id": "team_availability",
                "title": "Out of Office Today",
                "template": "widgets/home/absent.html",
                "ctx": {
                    'absent_today': self._get_absent_today()
                },
                "perm": "employee.view_employee",
                "col": "col-lg-4",
                "visible": True
            },
            #{
            #    "id": "holidays",
            #    "title": "{% trans 'Upcoming Holidays' %}",
            #    "template": "widgets/home/holidays.html",
            #    "ctx": {'holidays': self._get_upcoming_holidays()},
            #    "perm": "leave.view_holiday",
            #    "col": "col-lg-4",
            #    "visible": True
            #},
            {
                "id": "celebrations",
                "title": "Celebrations",
                "template": "widgets/home/celebrations.html",
                "ctx": {
                    'celebrations': self._get_celebrations(), 
                    'today': timezone.localdate()
                },
                "perm": "employee.view_employee",
                "col": "col-lg-4",
                "visible": True
            },
            {
                "id": "company_news",
                "title": "Announcements",
                "template": "widgets/home/announcements.html",
                "ctx": {
                    'notice': self._get_latest_notice()
                },
                "perm": "core.view_notice",
                "col": "col-lg-4",
                "visible": True
            }
        ]

        # Filter by visibility logic and Django permissions
        return [
            {
                "title": w["title"],
                "column": w["col"],
                "content": mark_safe(render_to_string(w["template"], w["ctx"], request=self.request))
            }
            for w in all_widgets if w["visible"] and user.has_perm(w["perm"])
        ]