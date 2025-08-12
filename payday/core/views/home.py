from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.shortcuts import render
from django.views import View
from django.utils.translation import gettext as _
from django.db.models import Count, Sum, Q
from django.apps import apps
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone


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
            'remaining_leave_days': self._get_remaining_leave_days(request),
            'statistics': self._get_employee_statistics(request),
            'leaves': self._get_pending_leaves(request),
            'payslips': self._get_current_year_payslips(request),
            'payroll_data': self._get_payroll_chart_data(),
        }

    def _get_employee_statistics(self, request):
        Employee = apps.get_model('employee', 'Employee')
        suborg = getattr(request.suborganization, "name", None)
        return Employee.objects.for_user(user=request.user)\
            .filter(sub_organization=suborg)\
            .values('status__name')\
            .annotate(count=Count('status__name'))

    def _get_pending_leaves(self, request):
        Leave = apps.get_model('leave', 'Leave')
        suborg = getattr(request.suborganization, "name", None)
        return Leave.objects.for_user(user=request.user)\
            .filter(status='pending', sub_organization=suborg)

    def _get_remaining_leave_days(self, request):
        # TODO: Replace with actual leave balance logic
        return 0

    def _get_current_year_payslips(self, request):
        sub_organization = getattr(request.suborganization, "name", None)
        PaidEmployee = apps.get_model('payroll', 'PaidEmployee')
        
        current_year = timezone.now().year
        qs = PaidEmployee.objects.for_user(user=request.user).filter(
            payroll__end_dt__year=current_year, 
            sub_organization=sub_organization
        )

        if any([
            request.user.is_superuser,
            request.user.is_staff
        ]):
            return qs[:36]
        return qs.filter(employee__user=request.user)[:36]

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
                "column": "col-12 col-md-6 col-lg-3",
                "visible": any([
                    self.request.user.is_staff,
                    self.request.user.is_superuser
                ])
            },
            {
                "title": _("Leave Request Form"),
                "content": render_to_string('widgets/home/leave_request_form.html', {
                    'remaining_leave_days': context['remaining_leave_days']
                }, request=request),
                "permission": "leave.add_leave",
                "column": "col-12 col-md-6 col-lg-3",
                "visible": True
            },
            {
                "title": _("Pending Leaves List"),
                "content": render_to_string('widgets/home/pending_leaves_list.html', {
                    'leaves': context['leaves']
                }, request=request),
                "permission": "leave.view_leave",
                "column": "col-12 col-md-6 col-lg-3",
                "visible": any([
                    self.request.user.is_staff,
                    self.request.user.is_superuser
                ])
            }
        ]
