from employee.models import Employee as EmployeeModel
from payroll.models import Payroll, PaidEmployee
from employee.models import Attendance
from django.conf import settings
from django.db import models
import pandas as pd
import validators
import os


class PayrollProcessor:
    def __init__(self, payroll):
        self.payroll = payroll

    def duplicate(self):
        df = self._get_employee_data()
        df = self._merge_with_native_attendance(df)
        df = self._merge_with_canvas_attendance(df)
        self._create_paid_employees(df)

    @staticmethod
    def _get_field_name(name):
        return name.split('__')[0]

    @staticmethod
    def _is_relation(field):
        return field.is_relation and field.get_internal_type() in ['ForeignKey', 'OneToOneField', 'ModelSelectField']

    def _get_date_time_field(self):
        return [field for field in EmployeeModel._meta.fields if 'date' in field.get_internal_type().lower()]

    def _get_employee_data(self):
        exclude = ['id', 'user', 'created_at', 'updated_at', 'created_by', 'updated_by', 'photo', 'email', 'phone', 'create_user_on_save']
        fields = [field for field in EmployeeModel._meta.fields if field.name not in exclude]
        fields = [f"{f.name}__name" if self._is_relation(f) else f.name for f in fields]
        fields += ["working_days_per_month", "children"]

        employees = EmployeeModel.objects.all().annotate(
            working_days_per_month=models.F('designation__working_days_per_month'),
            children=models.functions.Coalesce(models.Count('child'), models.Value(0)),
        ).values(*fields)

        df = pd.DataFrame.from_records(employees)
        df['mobile_number'] = df['mobile_number'].astype(str)
        df['registration_number'] = df['registration_number'].astype(str)  # Fix 1

        df['working_days_per_month'] = df['working_days_per_month'].fillna(0)
        df['attendance'] = df['working_days_per_month']

        df.columns = [self._get_field_name(c) for c in df.columns]
        df['employee_id'] = df['registration_number']
        df['payroll_id'] = self.payroll.id

        return df

    def _merge_with_native_attendance(self, df):
        attendances = Attendance.objects.filter(checked_at__date__range=(self.payroll.start_dt, self.payroll.end_dt))
        attendances = attendances.values('employee__registration_number').annotate(attendance=models.Count('employee__registration_number'))

        if not attendances:
            return df

        attendances = pd.DataFrame.from_records(attendances)
        attendances['employee__registration_number'] = attendances['employee__registration_number'].astype(str)  # Fix 2
        df['registration_number'] = df['registration_number'].astype(str)  # Ensure consistency

        df = pd.merge(df, attendances, how='left', left_on='registration_number', right_on='employee__registration_number')
        df['attendance'] = df.apply(lambda x: min(x['attendance_x'], x['attendance_y']) if pd.notnull(x['attendance_y']) else x['attendance_x'], axis=1)
        df = df.drop(columns=['attendance_y', 'attendance_x', 'employee__registration_number'])

        return df

    def _merge_with_canvas_attendance(self, df):
        canvas = self.payroll.canvas
        if not canvas or not canvas.url:
            return df

        file_obj = getattr(canvas, 'url', canvas)
        if not validators.url(file_obj) and settings.DEBUG:
            file_obj = os.path.join(os.getcwd(), file_obj)

        _df = pd.read_excel(file_obj, dtype={'registration_number': str})  # Fix 3
        if _df.empty:
            return df

        _df.fillna(0, inplace=True)
        _df[_df.columns[0]] = _df[_df.columns[0]].astype(str)  # Ensure string dtype
        df['registration_number'] = df['registration_number'].astype(str)  # Ensure string dtype again

        _df = _df[[_df.columns[0], 'absence']]
        df = pd.merge(df, _df, how='left', left_on='registration_number', right_on=_df.columns[0])

        df['attendance'] = df['attendance'] - df['absence']
        return df.drop(columns=['absence', _df.columns[0]])

    def _create_paid_employees(self, df):
        paid_employees = [PaidEmployee(**employee) for employee in df.to_dict('records')]
        PaidEmployee.objects.bulk_create(paid_employees)
