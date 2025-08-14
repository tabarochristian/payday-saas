from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.shortcuts import render
from django.views import View
from django.utils.translation import gettext as _
from django.db.models import Count, Sum, Q
from django.apps import apps
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum, F, ExpressionWrapper, DurationField


class Home(LoginRequiredMixin, View):
    """
    Dashboard view that dynamically renders widgets based on user permissions and role.
    """
    template_name = "home.html"

    def get(self, request):
        """
        Handle GET request and render dashboard with authorized widgets.
        """
        widgets = self._get_authorized_widgets(request)
        return render(request, self.template_name, {'widgets': widgets})

    def _get_authorized_widgets(self, request):
        """
        Render widgets based on user permissions and admin status.
        """
        context = self._build_context(request)
        widget_definitions = self._widget_definitions(context, request)

        return [
            {
                "title": widget["title"],
                "column": widget["column"],
                "content": mark_safe(widget["content"]),
            }
            for widget in widget_definitions
            if request.user.has_perm(widget["permission"]) and widget.get("visible", False)
        ]

    def _build_context(self, request):
        """
        Aggregate all data needed for widget rendering.
        """
        return {
            'remaining_leaves': self._get_remaining_leaves(request),
            'statistics': self._get_employee_statistics(request),
            'payslips': self._get_current_year_payslips(request),
            'payroll_data': self._get_payroll_chart_data()
        }

    def _get_employee_statistics(self, request):
        Employee = apps.get_model('employee', 'Employee')
        suborg = getattr(request.suborganization, "name", None)
        return Employee.objects.for_user(user=request.user)\
            .filter(sub_organization=suborg)\
            .values('status__name')\
            .annotate(count=Count('status__name'))

    def _get_remaining_leaves(self, request):
        TypeOfLeave = apps.get_model('leave', 'TypeOfLeave')
        Leave = apps.get_model('leave', 'Leave')
        current_year = timezone.now().year

        # Get all leave durations for the employee this year
        leaves = Leave.objects.for_user(user=request.user).filter(
            Q(employee__email=request.user.email) | Q(employee__user=request.user)
        ).filter(
            start_date__year=current_year,
            status='APPROVED'
        ).annotate(
            used_days = ExpressionWrapper(
                F('end_date') - F('start_date') + timedelta(days=1),
                output_field=DurationField()
            )
        )

        # Aggregate used days per type
        used_by_type = leaves.values('type_of_leave__id', 'type_of_leave__name').annotate(
            total_used=Sum('used_days')
        )

        # Convert to dict for easy lookup
        used_map = {item['type_of_leave__id']: item['total_used'].days for item in used_by_type}

        # Prepare final list
        remaining = []
        for leave_type in TypeOfLeave.objects.all():
            used = used_map.get(leave_type.id, 0)
            remaining_days = max(leave_type.max_duration - used, 0)
            remaining.append({
                'allowed': leave_type.max_duration,
                'remaining': remaining_days,
                'type': leave_type.name,
                'used': used,
            })
        return remaining

    def _get_current_year_payslips(self, request):
        sub_organization = getattr(request.suborganization, "name", None)
        PaidEmployee = apps.get_model('payroll', 'PaidEmployee')
        
        qs = PaidEmployee.objects.filter(
            payroll__end_dt__year=timezone.now().year, 
            sub_organization=sub_organization,
        ).filter(
            Q(employee__user=request.user) | Q(employee__email=request.user.email)
        )

        return qs[:36]

    def _get_payroll_chart_data(self):
        Payroll = apps.get_model('payroll', 'Payroll')
        qs = Payroll.objects.values('name')\
            .annotate(total=Sum('overall_net'))\
            .order_by('-created_at')

        return {
            'names': [entry['name'] for entry in qs],
            'amounts': [float(entry['total']) for entry in qs],
        }

    def _widget_definitions(self, context, request):
        """
        Define all widgets with metadata and rendered content.
        """
        return [
            {
                "title": _("Salary Statistics"),
                "content": render_to_string('widgets/home/salary_statistics_chart.html', {
                    'payroll_data': context['payroll_data']
                }, request=request),
                "permission": "payroll.view_paidemployee",
                "column": "col-12",
                "visible": any([
                    self.request.user.is_staff,
                    self.request.user.is_superuser
                ])
            },
            {
                "title": _("Current Year Payslips"),
                "content": render_to_string('widgets/home/current_year_payslips.html', {
                    'payslips': context['payslips']
                }, request=request),
                "permission": "payroll.view_paidemployee",
                "column": "col-12",
                "visible": True
            },
            {
                "title": _("Employee Status Cards"),
                "content": render_to_string('widgets/home/employee_status_cards.html', {
                    'statistics': context['statistics']
                }, request=request),
                "permission": "employee.view_employee",
                "column": "col-12 col-md-6 col-lg-4",
                "visible": any([
                    self.request.user.is_staff,
                    self.request.user.is_superuser
                ])
            },
            {
                "title": _("Leave Request Form"),
                "content": render_to_string(
                    'widgets/home/leave_request_form.html', 
                    dict(), 
                    request=request
                ),
                "permission": "leave.add_leave",
                "column": "col-12 col-md-6 col-lg-4",
                "visible": True
            },
            {
                "title": _("Pending Leaves List"),
                "content": render_to_string('widgets/home/pending_leaves_list.html', {
                    'remaining_leaves': context['remaining_leaves']
                }, request=request),
                "permission": "leave.view_leave",
                "column": "col-12 col-md-6 col-lg-4",
                "visible": True
            }
        ]
