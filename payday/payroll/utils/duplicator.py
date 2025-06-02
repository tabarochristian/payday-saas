# payroll/services/payroll_processor.py

from django.conf import settings
from django.db import models
import pandas as pd
import validators
import time
import os
from typing import Any, Dict, List, Optional

from employee.models import Employee as EmployeeModel, Attendance
from payroll.models import PaidEmployee


class PayrollProcessor:
    """
    Handles payroll computation by merging employee data with attendance.
    """

    def __init__(self, payroll, schema='public'):
        self.payroll = payroll
        self.employee_fields = []
        self.exclude_fields = {
            "id", "user", "created_at", "updated_at",
            "created_by", "updated_by", "photo", "email", "phone", "create_user_on_save"
        }
        
    def process(self):
        """Main entry point to start processing."""
        time.sleep(1)
        self.statues = self.payroll.employee_status.all()\
            .values_list('name', flat=True).distinct()
        df = self._get_employee_data()
        df = self._merge_with_native_attendance(df)
        df = self._merge_with_canvas_attendance(df)
        self._save_paid_employees(df)

    def _get_field_name(self, name: str) -> str:
        return name.split("__")[0]

    def _is_relation(self, field: models.Field) -> bool:
        return field.is_relation and field.get_internal_type() in [
            "ForeignKey",
            "OneToOneField",
        ]

    def _get_date_time_fields(self) -> List[models.Field]:
        return [
            field for field in EmployeeModel._meta.fields
            if "date" in field.get_internal_type().lower()
        ]

    from django.db import models

    def _get_employee_queryset(self):
        fields = [f.name for f in EmployeeModel._meta.fields if f.name not in self.exclude_fields]
        
        annotate_fields = {
            "working_days_per_month": models.functions.Coalesce(
                models.F("designation__working_days_per_month"), models.Value(23)
            ),
            "children": models.functions.Coalesce(models.Count("child"), models.Value(0)),
        }
    
        return (
            EmployeeModel.objects.filter(status__name__in=self.statues)\
            .annotate(**annotate_fields)\
            .values(*fields, *annotate_fields.keys())
        )


    def _get_employee_data(self) -> pd.DataFrame:
        """Load and format employee data into a DataFrame."""
        employees = self._get_employee_queryset()
        if not employees:
            return pd.DataFrame()

        df = pd.DataFrame.from_records(employees)

        # Ensure string-based registration number
        df["registration_number"] = df["registration_number"].astype(str)
        df["mobile_number"] = df["mobile_number"].astype(str)
        df["attendance"] = df["working_days_per_month"].fillna(0)

        # Rename columns
        df.columns = [self._get_field_name(col) for col in df.columns]
        df["employee_id"] = df["registration_number"]
        df["payroll_id"] = self.payroll.id

        return df

    def _merge_with_native_attendance(self, df: pd.DataFrame) -> pd.DataFrame:
        """Merge with internal attendance records."""
        attendances = (
            Attendance.objects.filter(
                checked_at__date__range=(self.payroll.start_dt, self.payroll.end_dt)
            )
            .values("employee__registration_number")
            .annotate(attendance=models.Count("employee__registration_number"))
        )

        if not attendances:
            return df

        attendance_df = pd.DataFrame.from_records(attendances)
        attendance_df["employee__registration_number"] = attendance_df[
            "employee__registration_number"
        ].astype(str)
        df["registration_number"] = df["registration_number"].astype(str)

        merged_df = pd.merge(
            df,
            attendance_df,
            how="left",
            left_on="registration_number",
            right_on="employee__registration_number",
        )

        merged_df["attendance"] = merged_df.apply(
            lambda x: min(x["attendance"], x["attendance_y"])
            if pd.notnull(x["attendance_y"])
            else x["attendance"],
            axis=1,
        )

        return merged_df.drop(
            columns=["attendance_y", "attendance_x", "employee__registration_number"],
            errors="ignore",
        )

    def _merge_with_canvas_attendance(self, df: pd.DataFrame) -> pd.DataFrame:
        """Merge with external attendance Excel file."""
        if not self.payroll.canvas:
            return df

        canvas_url = getattr(self.payroll.canvas, "url", None)

        try:
            file_path = self._resolve_file_path(canvas_url)
            
            # ✅ Check if the file exists before reading
            if not os.path.exists(file_path):
                print(f"Canvas attendance file not found: {file_path}")
                return df

            canvas_df = pd.read_excel(file_path, dtype={"registration_number": str})

            if canvas_df.empty:
                return df

            canvas_df.fillna(0, inplace=True)
            canvas_df[canvas_df.columns[0]] = canvas_df[canvas_df.columns[0]].astype(str)
            df["registration_number"] = df["registration_number"].astype(str)

            df = pd.merge(
                df,
                canvas_df[[canvas_df.columns[0], "absence"]],
                how="left",
                left_on="registration_number",
                right_on=canvas_df.columns[0],
            )

            df["attendance"] = df["attendance"] - df.get("absence", 0)
            return df.drop(columns=["absence", canvas_df.columns[0]], errors="ignore")

        except Exception as e:
            print(f"Error reading canvas attendance: {e}")
            return df

    def _resolve_file_path(self, url: str) -> str:
        """Resolve URL or local path"""
        if validators.url(url):
            return url
        elif settings.DEBUG:
            return os.path.join(os.getcwd(), url)
        raise ValueError(f"Invalid canvas file path: {url}")

    def _save_paid_employees(self, df: pd.DataFrame):
        """Bulk create PaidEmployee entries from processed DataFrame."""
        if df.empty:
            return

        paid_employees = [PaidEmployee(**record) for record in df.to_dict("records")]
        PaidEmployee.objects.bulk_create(paid_employees)#, ignore_conflicts=True)