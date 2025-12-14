from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.shortcuts import render
from django.views import View
from django.utils.translation import gettext as _
from django.db.models import Count, Sum, Q, F, ExpressionWrapper, DurationField
from django.apps import apps
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from datetime import timedelta
# Removed redundant imports (Sum, F, ExpressionWrapper, DurationField are already in the main import)

# --- Constants for better readability ---
LEAVE_STATUS_APPROVED = 'APPROVED'
PAYROLL_STATUS_APPROVED = 'APPROVED'


class Home(LoginRequiredMixin, View):
    """
    Dashboard view that dynamically renders widgets based on user permissions and role.
    This view depends on 'employee', 'leave', and 'payroll' apps being installed
    and the user having a related 'employee' object.
    """
    template_name = "home.html"
    
    # --- Helper to access models lazily/cleanly ---
    def _get_model(self, app_label, model_name):
        return apps.get_model(app_label, model_name)

    def get(self, request):
        """
        Handle GET request and render dashboard with authorized widgets.
        """
        context = self._build_context(request)
        widgets = self._get_authorized_widgets(request, context)
        return render(request, self.template_name, {'widgets': widgets})

    # --- Renamed to accept context, making method signature cleaner ---
    def _get_authorized_widgets(self, request, context):
        """
        Render widgets based on user permissions and admin status.
        
        Args:
            request: The current request object.
            context: The pre-calculated data context for widgets.
        """
        widget_definitions = self._widget_definitions(context, request)

        return [
            {
                "title": widget["title"],
                # Standard practice: column classes should be consistent
                "column": widget.get("column", "col-12"), 
                "content": mark_safe(widget["content"]),
            }
            for widget in widget_definitions
            # Use request.user.has_perm and check visibility
            if widget.get("visible", False) and request.user.has_perm(widget["permission"])
        ]

    def _build_context(self, request):
        """
        Aggregate all data needed for widget rendering.
        Memoization could be added here for complex calculations if needed,
        but for simplicity, we call the individual data-fetching methods.
        """
        try:
            employee = request.user.employee
        except AttributeError:
            employee = None

        # Sub-organization is often critical for HR/Payroll data isolation
        sub_organization = getattr(request, "suborganization", None)
        
        return {
            'remaining_leaves': self._get_remaining_leaves(request),
            'statistics': self._get_employee_statistics(request, sub_organization),
            'payslips': self._get_current_year_payslips(request, sub_organization),
            'payroll_data': self._get_payroll_chart_data(),
            'attendance': self._get_employee_attend(employee),
            'employee': employee,
            'is_admin_or_staff': request.user.is_staff or request.user.is_superuser
        }

    # --- Accept 'employee' object directly for cleaner method signature and re-use ---
    def _get_employee_attend(self, employee):
        """Fetches today's attendance record for the employee."""
        Attendance = self._get_model('employee', 'Attendance')
        
        today = timezone.localdate() # Use localdate for date-only comparison
        
        try:
            return Attendance.objects.filter(
                employee=employee,
                # Use __date lookup on DateTimeField for efficiency
                first_checked_at__date=today, 
            ).order_by('-first_checked_at').first()
        except Exception:
            # Log the exception for debugging if necessary
            return None

    def _get_employee_statistics(self, request, sub_organization):
        """Counts employees by status, filtered by sub-organization."""
        Employee = self._get_model('employee', 'Employee')
        
        # NOTE: If Employee.objects.for_user() already handles sub_organization 
        # filtering, you should remove the .filter(sub_organization=...) line to 
        # avoid redundant filtering. Assuming it's necessary here.
        queryset = Employee.objects.for_user(user=request.user)
        if sub_organization:
             queryset = queryset.filter(sub_organization=sub_organization)

        return queryset.values('status__name').annotate(count=Count('status__name'))

    def _get_remaining_leaves(self, request):
        """Calculates remaining leave days per type for the current user."""
        TypeOfLeave = self._get_model('leave', 'TypeOfLeave')
        Leave = self._get_model('leave', 'Leave')
        
        current_year = timezone.now().year

        # 1. Filter Leaves: Use ORM filter on employee relationship directly
        # The Q(employee__email=...) is often redundant if the user has an employee profile
        # linked to request.user. Simplify to:
        leaves_qs = Leave.objects.filter(
            employee__user=request.user, # Assumes a one-to-one relationship
            start_date__year=current_year,
            status=LEAVE_STATUS_APPROVED
        ).annotate(
            # ExpressionWrapper for precise duration calculation
            used_days = ExpressionWrapper(
                F('end_date') - F('start_date') + timedelta(days=1),
                output_field=DurationField()
            )
        )

        # 2. Aggregate Used Days
        # Uses one query for aggregation
        used_by_type = leaves_qs.values('type_of_leave__id', 'type_of_leave__name').annotate(
            total_used=Sum('used_days')
        )
        
        # Convert aggregation results to a dictionary map
        # Dictionary comprehension is cleaner
        used_map = {
            item['type_of_leave__id']: item['total_used'].days 
            for item in used_by_type
        }

        # 3. Combine with TypeOfLeave: Reduces query count from N+1 to 2
        all_leave_types = TypeOfLeave.objects.all().order_by('name')
        
        remaining = []
        for leave_type in all_leave_types:
            used = used_map.get(leave_type.id, 0)
            remaining_days = max(leave_type.max_duration - used, 0)
            remaining.append({
                'allowed': leave_type.max_duration,
                'remaining': remaining_days,
                'type': leave_type.name,
                'used': used,
            })
            
        return remaining

    def _get_current_year_payslips(self, request, sub_organization):
        """Fetches up to 36 payslips for the current user this year."""
        PaidEmployee = self._get_model('payroll', 'PaidEmployee')
        
        # Ensure filtering uses the most direct ORM relationship (employee__user)
        qs = PaidEmployee.objects.filter(
            payroll__end_dt__year=timezone.now().year, 
            sub_organization=sub_organization,
            employee__user=request.user, # Assumes 1:1 user->employee relationship
        ).order_by('-payroll__end_dt') # Order by most recent for relevance

        return qs[:36]

    def _get_payroll_chart_data(self):
        """Aggregates approved payroll net amounts."""
        Payroll = self._get_model('payroll', 'Payroll')
        
        qs = Payroll.objects.filter(
            status=PAYROLL_STATUS_APPROVED
        ).values('name').annotate(
            total=Sum('overall_net')
        ).order_by('-created_at')

        # Use list comprehension for cleaner dict/list construction
        return {
            'names': [entry['name'] for entry in qs],
            # Avoid float() conversion if 'overall_net' is DecimalField.
            # Convert to str() for template display or keep as Decimal.
            # Assuming float is needed for a JS chart library.
            'amounts': [float(entry['total']) for entry in qs],
        }

    def _widget_definitions(self, context, request):
        """
        Define all widgets with metadata and rendered content.
        This is now cleaner due to pre-calculated context variables.
        """
        employee = context.get('employee')
        is_admin_or_staff = context.get('is_admin_or_staff', False)
        
        # --- Common Visibility Checks ---
        is_visible_to_admin = is_admin_or_staff
        is_visible_to_employee = True # Most employee widgets are always visible
        
        # Accessing employee.web_devices needs a null check
        has_web_devices = getattr(employee, 'web_devices', False) if employee else False

        return [
            {
                "title": _("Attendance"),
                "content": render_to_string('widgets/home/attend.html', {
                    'attendance': context.get('attendance', None)
                }, request=request),
                "permission": "payroll.view_paidemployee", # Check if this permission is appropriate for a basic attendance widget
                "column": "col-12",
                "visible": has_web_devices
            },
            {
                "title": _("Salary Statistics"),
                "content": render_to_string('widgets/home/salary_statistics_chart.html', {
                    'payroll_data': context.get('payroll_data', None)
                }, request=request),
                "permission": "payroll.view_paidemployee",
                "column": "col-12",
                "visible": is_visible_to_admin
            },
            {
                "title": _("Current Year Payslips"),
                "content": render_to_string('widgets/home/current_year_payslips.html', {
                    'payslips': context.get('payslips', None)
                }, request=request),
                "permission": "payroll.view_paidemployee",
                "column": "col-12 col-md-6 col-lg-4",
                "visible": is_visible_to_employee
            },
            {
                "title": _("Employee Status Cards"),
                "content": render_to_string('widgets/home/employee_status_cards.html', {
                    'statistics': context.get('statistics', None)
                }, request=request),
                "permission": "employee.view_employee",
                "column": "col-12 col-md-6 col-lg-4",
                "visible": is_visible_to_admin
            },
            {
                "title": _("Leave Request Form"),
                "content": render_to_string(
                    'widgets/home/leave_request_form.html', 
                    {}, # Empty dict is clearer than dict()
                    request=request
                ),
                "permission": "leave.add_leave",
                "column": "col-12 col-md-6 col-lg-4",
                "visible": is_visible_to_employee
            },
            {
                "title": _("Pending Leaves List"),
                "content": render_to_string('widgets/home/pending_leaves_list.html', {
                    'remaining_leaves': context['remaining_leaves']
                }, request=request),
                "permission": "leave.view_leave",
                "column": "col-12 col-md-6 col-lg-4",
                "visible": is_visible_to_employee
            }
        ]