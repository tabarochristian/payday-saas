from datetime import timedelta

from django.apps import apps
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum, Q, F, ExpressionWrapper, DurationField
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.generic import TemplateView


class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "home.html"
    sub_organization = None 

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user
        employee = getattr(user, "employee", None)

        sub_organization = getattr(self.request, "suborganization", None)
        self.sub_organization = sub_organization

        today = timezone.localdate()

        # Pre-fetch reusable datasets (prevents repeated DB hits)
        cache = {
            "attendance": self.get_today_attendance(employee, today),
            "leave_balances": self.get_leave_balances(employee),
            "pending_leaves": self.get_pending_leaves(employee),
            "absent_today": self.get_absent_today(employee, today),
            # "holidays": self.get_upcoming_holidays(today),
            "celebrations": self.get_celebrations(today),

            "admin_stats": self.get_admin_metrics(user),
            "latest_notice": self.get_latest_notice(),
        }

        context["widgets"] = self.build_widgets(user, employee, cache)
        return context

    # ------------------------------------------------------------------
    # Data Fetching (Queries Only)
    # ------------------------------------------------------------------

    def get_today_attendance(self, employee, today):
        if not employee:
            return None

        Attendance = apps.get_model("employee", "Attendance")
        return (
            Attendance.objects
            .filter(
                sub_organization=self.sub_organization,
                employee=employee, 
                first_checked_at__date=today
            )
            .first()
        )

    def get_leave_balances(self, employee):
        """Aggregate leave usage per leave type for the current year."""
        if not employee:
            return []

        TypeOfLeave = apps.get_model("leave", "TypeOfLeave")
        current_year = timezone.now().year

        return (
            TypeOfLeave.objects.filter(
                sub_organization=self.sub_organization
            ).annotate(
                used=Sum(
                    ExpressionWrapper(
                        F("leave__end_date") - F("leave__start_date") + timedelta(days=1),
                        output_field=DurationField(),
                    ),
                    filter=Q(
                        leave__employee=employee,
                        leave__start_date__year=current_year,
                        leave__status="APPROVED",
                    ),
                )
            )
            .values("name", "max_duration", "used")
        )

    def get_pending_leaves(self, employee):
        if not employee:
            return []

        Leave = apps.get_model("leave", "Leave")
        return (
            Leave.objects
            .filter(
                sub_organization = self.sub_organization,
                employee=employee, 
                status="PENDING"
            ).select_related("employee")[:5]
        )

    def get_absent_today(self, employee, today):
        if not employee:
            return []

        Leave = apps.get_model("leave", "Leave")
        return (
            Leave.objects
            .filter(
                status="APPROVED",
                start_date__lte=today,
                end_date__gte=today,
                sub_organization=self.sub_organization
            )
            .select_related("employee")
            .order_by("-start_date")[:6]
        )

    # def get_upcoming_holidays(self, today):
    #     Holiday = apps.get_model("leave", "holiday")
    #     return (
    #         Holiday.objects
    #         .filter(
    #             start_date__gte=today, 
    #             sub_organization=self.sub_organization
    #         ).order_by("start_date")[:3]
    #     )

    def get_celebrations(self, today):
        Employee = apps.get_model("employee", "Employee")
        return (
            Employee.objects
            .filter(
                Q(date_of_birth__month=today.month)
                | Q(date_of_join__month=today.month),
                sub_organization=self.sub_organization
            )
            .order_by("date_of_birth__day")[:5]
        )

    def get_latest_notice(self):
        """Placeholder for announcements."""
        return None

    def get_admin_metrics(self, user):
        if not user.is_staff and not user.is_superuser:
            return None

        Employee = apps.get_model("employee", "Employee")
        qs = Employee.objects.for_user(user)\
            .filter(sub_organization=self.sub_organization)

        return qs.values("status__name").annotate(count=Count("id"))

    # ------------------------------------------------------------------
    # Widget Engine
    # ------------------------------------------------------------------

    def build_widgets(self, user, employee, cache):
        widgets = [
            {
                "title": "Clock In / Out",
                "template": "widgets/home/attend.html",
                "context": {"attendance": cache["attendance"]},
                "perm": "employee.view_attendance",
                "column": "col-lg-12",
                "visible": bool(employee and employee.web_attendance().exists()),
            },
            {
                "title": "Pending Requests",
                "template": "widgets/home/pending.html",
                "context": {"pending_leaves": cache["pending_leaves"]},
                "perm": "leave.change_leave",
                "column": "col-lg-8",
                "visible": bool(cache["pending_leaves"]),
            },
            {
                "title": "Organization Overview",
                "template": "widgets/home/stats.html",
                "context": {"stats": cache["admin_stats"]},
                "perm": "employee.view_employee",
                "column": "col-lg-4",
                "visible": bool(cache["admin_stats"]),
            },
            {
                "title": "My Leave Balances",
                "template": "widgets/home/leaves.html",
                "context": {"leaves": cache["leave_balances"]},
                "perm": "leave.view_leave",
                "column": "col-lg-4",
                "visible": bool(employee),
            },
            {
                "title": "Out of Office Today",
                "template": "widgets/home/absent.html",
                "context": {"absent_today": cache["absent_today"]},
                "perm": "employee.view_employee",
                "column": "col-lg-4",
                "visible": bool(cache["absent_today"]),
            },
            # {
            #     "title": "Upcoming Holidays",
            #     "template": "widgets/home/holidays.html",
            #     "context": {"holidays": cache["holidays"]},
            #     "perm": "leave.view_holiday",
            #     "column": "col-lg-4",
            #     "visible": bool(cache["holidays"]),
            # },
            {
                "title": "Celebrations",
                "template": "widgets/home/celebrations.html",
                "context": {
                    "celebrations": cache["celebrations"],
                    "today": timezone.localdate(),
                },
                "perm": "employee.view_employee",
                "column": "col-lg-4",
                "visible": bool(cache["celebrations"]),
            },
            {
                "title": "Announcements",
                "template": "widgets/home/announcements.html",
                "context": {"notice": cache["latest_notice"]},
                "perm": "core.view_notice",
                "column": "col-lg-4",
                "visible": bool(cache["latest_notice"]),
            },
        ]

        return [
            self.render_widget(w)
            for w in widgets
            if w["visible"] and user.has_perm(w["perm"])
        ]

    def render_widget(self, widget):
        """Render a widget safely and consistently."""
        html = render_to_string(
            widget["template"],
            widget["context"],
            request=self.request,
        )
        return {
            "title": widget["title"],
            "column": widget["column"],
            "content": mark_safe(html),
        }
