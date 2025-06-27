from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.shortcuts import render
from django.views import View
from django.utils.translation import gettext as _
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Count, Sum
from django.apps import apps
from django.contrib.auth.mixins import LoginRequiredMixin
from core.forms import modelform_factory
from django.utils import timezone
import json

class Home(LoginRequiredMixin, View):
    """
    Optimized Home view that renders dashboard widgets conditionally based on permissions.
    """
    template_name = "home.html"

    def get_context_data(self, request):
        return {
            'remaining_leave_days': self.get_remaining_leave_days(),
            'statistics': self.get_statistics(),
            'leaves': self.get_leaves(),
            'payslips': self.get_payslips(),
            'payroll_data': self.get_payroll_data(),
        }

    def get_statistics(self):
        """Get employee count by status."""
        model = apps.get_model('employee', 'Employee')
        return model.objects.for_user(user=self.request.user)\
            .values('status__name').annotate(count=Count('status__name'))

    def get_leaves(self):
        """Get all pending leave requests."""
        model = apps.get_model('leave', 'Leave')
        return model.objects.for_user(user=self.request.user).\
            filter(status='pending')

    def get_remaining_leave_days(self):
        """Stub: Replace with real logic."""
        return 0

    def get_payslips(self):
        """Get current year payslips for logged-in user."""
        model = apps.get_model('payroll', 'PaidEmployee')
        return model.objects.for_user(user=self.request.user).filter(
            payroll__end_dt__year=timezone.now().date().year
        )

    def get_payroll_data(self):
        """Get monthly salary data for chart."""
        model = apps.get_model('payroll', 'Payroll')
        qs = model.objects.values('name') \
            .annotate(amounts=Sum('overall_net')) \
            .order_by('-created_at')

        names = [data['name'] for data in qs]
        amounts = [float(data['amounts']) for data in qs]

        return {
            'names': names,
            'amounts': amounts
        }

    def get_widgets(self, request):
        """Generate list of widgets filtered by user permissions."""
        context = self.get_context_data(request)

        widgets = [
            {
                "title": _("Salary Statistics"),
                "content": render_to_string('widgets/home/salary_statistics_chart.html', {
                    'payroll_data': context['payroll_data']
                }, request=request),
                "permission": "payroll.view_paidemployee",
                "column": "col-12"
            },
            {
                "title": _("Employee Status Cards"),
                "content": render_to_string('widgets/home/employee_status_cards.html', {
                    'statistics': context['statistics']
                }, request=request),
                "permission": "employee.view_employee",
                "column": "col-12 col-md-6 col-lg-3"
            },
            {
                "title": _("Leave Request Form"),
                "content": render_to_string('widgets/home/leave_request_form.html', {
                    'remaining_leave_days': context['remaining_leave_days'],
                }, request=request),
                "permission": "leave.add_leave",
                "column": "col-12 col-md-6 col-lg-3"
            },
            {
                "title": _("Pending Leaves List"),
                "content": render_to_string('widgets/home/pending_leaves_list.html', {
                    'leaves': context['leaves']
                }, request=request),
                "permission": "leave.view_leave",
                "column": "col-12 col-md-6 col-lg-3"
            },
            {
                "title": _("Current Year Payslips"),
                "content": render_to_string('widgets/home/current_year_payslips.html', {
                    'payslips': context['payslips']
                }, request=request),
                "permission": "payroll.view_paidemployee",
                "column": "col-12 col-md-6 col-lg-6"
            }
        ]

        return [{
            "title": widget["title"],
            "column": widget["column"],
            "content": mark_safe(widget["content"]),
        } for widget in widgets if request.user.has_perm(widget["permission"])]

    def get(self, request):
        """
        Handle GET requests for the homepage.

        Retrieves all Widget objects and prepares a list where each widget is represented
        as a dictionary containing its title, rendered content, and assigned column.
        The resulting context is then rendered with the specified template.

        Args:
            request (HttpRequest): The HTTP request object.

        Returns:
            HttpResponse: The rendered template response with the widget information.
        """
        # Retrieve all widgets and build a list of dictionaries for each one.
        widgets = [widget for widget in self.get_widgets(request) if widget['content']]

        Widget = apps.get_model('core', model_name='widget')
        widgets += [{
            'title': widget.name,
            'content': widget.render(request),
            'column': widget.column,
        } for widget in Widget.objects.all()]
        return render(request, self.template_name, locals())
