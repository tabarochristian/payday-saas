# payroll/services/payroll_processor.py

import logging
import os
import time
from typing import Any, Dict, List, Optional

import pandas as pd
import validators
from django.conf import settings
from django.db import models

from employee.models import Employee as EmployeeModel, Attendance
from payroll.models import PaidEmployee
from core.utils import set_schema
from leave.models import Leave
from datetime import timedelta

# Configure logger
logger = logging.getLogger(__name__)

class PayrollProcessor:
    """
    Handles payroll computation by merging employee data with attendance.
    """

    def __init__(self, payroll, schema='public'):
        self.schema = schema
        self.payroll = payroll
        self.employee_fields = []
        self.exclude_fields = {
            "id", "user", "created_at", "updated_at",
            "created_by", "updated_by", "photo", "email", "phone", "create_user_on_save"
        }
        logger.debug(f"Initialized PayrollProcessor for payroll ID {payroll.id} with schema {schema}")

    def process(self):
        """Main entry point to start processing."""
        logger.info(f"Starting payroll processing for payroll ID {self.payroll.id}")
        start_time = time.time()
        time.sleep(1)
        try:
            if self.schema != "public":
                set_schema(self.schema)
            self.statuses = self.payroll.employee_status.all().values_list('name', flat=True)
            logger.debug(f"Retrieved {len(self.statuses)} employee statuses")
            df = self._get_employee_data()
            df = self._merge_with_leave(df)
            df = self._merge_with_native_attendance(df)
            df = self._merge_with_canvas_attendance(df)
            self._save_paid_employees(df)
            logger.info(f"Payroll processing completed in {time.time() - start_time:.2f} seconds")
        except Exception as e:
            logger.error(f"Payroll processing failed: {str(e)}", exc_info=True)
            raise

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

    def _get_employee_queryset(self):
        fields = ["pk"] + [f.name for f in EmployeeModel._meta.fields if f.name not in self.exclude_fields]
        
        annotate_fields = {
            "working_days_per_month": models.functions.Coalesce(
                models.F("designation__working_days_per_month"), models.Value(22)
            ),
            "children": models.functions.Coalesce(models.Count("child"), models.Value(0))
        }
    
        logger.debug(f"Building employee queryset with fields: {fields}")
        qs = EmployeeModel.objects.all()
        qs = qs.filter(status__name__in=self.statuses)
        return (
            qs.filter(sub_organization=self.payroll.sub_organization)
            .annotate(**annotate_fields)
            .values(*fields, *annotate_fields.keys())
        )

    def _get_employee_data(self) -> pd.DataFrame:
        """Load and format employee data into a DataFrame."""
        logger.info("Loading employee data into DataFrame")
        try:
            employees = self._get_employee_queryset()
            if not employees:
                logger.warning("No employee data found for the given statuses")
                return pd.DataFrame()

            df = pd.DataFrame.from_records(employees)
            logger.debug(f"Loaded {len(df)} employee records")

            # Ensure string-based registration number
            df["registration_number"] = df["registration_number"].astype(str)
            df["attendance"] = df["working_days_per_month"].fillna(0)
            df["mobile_number"] = df["mobile_number"].astype(str)

            # Rename columns
            df.columns = [self._get_field_name(col) for col in df.columns]
            df["sub_organization"] = self.payroll.sub_organization
            df["payroll_id"] = self.payroll.id
            df["employee_id"] = df["pk"]

            # delete the column pk
            del df["pk"]

            logger.debug("Employee data formatted successfully")
            return df
        except Exception as e:
            logger.error(f"Failed to load employee data: {str(e)}", exc_info=True)
            raise

    def _merge_with_leave(self, df: pd.DataFrame) -> pd.DataFrame:
        """Merge with approved leave records (paid and unpaid)."""
        logger.info("Merging with approved leave records")
        try:
            if df.empty:
                logger.warning("Empty employee DataFrame, skipping leave merge")
                return df

            queryset = Leave.objects.filter(
                start_date__lte=self.payroll.end_dt,
                end_date__gte=self.payroll.start_dt,
                status='APPROVED'
            ).annotate(
                leave_duration=models.ExpressionWrapper(
                    models.F('end_date') - models.F('start_date') + timedelta(days=1),
                    output_field=models.DurationField()
                )
            ).values('employee__registration_number').annotate(
                paid_leave_days=models.Sum(
                    models.Case(
                        models.When(type_of_leave__paid=True, then=models.F('leave_duration')),
                        default=timedelta(days=0),
                        output_field=models.DurationField()
                    )
                ),
                unpaid_leave_days=models.Sum(
                    models.Case(
                        models.When(type_of_leave__paid=False, then=models.F('leave_duration')),
                        default=timedelta(days=0),
                        output_field=models.DurationField()
                    )
                )
            )

            if not queryset:
                logger.warning("No approved leave records found")
                return df

            leave_df = pd.DataFrame.from_records(queryset)
            logger.debug(f"Loaded {len(leave_df)} leave records")

            # Convert timedelta to integer days
            leave_df['paid_leave_days'] = leave_df['paid_leave_days'].apply(lambda x: x.days if pd.notnull(x) else 0)
            leave_df['unpaid_leave_days'] = leave_df['unpaid_leave_days'].apply(lambda x: x.days if pd.notnull(x) else 0)

            # Ensure matching keys are strings
            leave_df['employee__registration_number'] = leave_df['employee__registration_number'].astype(str)
            df['registration_number'] = df['registration_number'].astype(str)

            # Merge with main DataFrame
            merged_df = pd.merge(
                df,
                leave_df,
                how="left",
                left_on="registration_number",
                right_on="employee__registration_number"
            )

            # Fill missing leave values with 0
            merged_df['paid_leave_days'] = merged_df['paid_leave_days'].fillna(0).astype(int)
            merged_df['unpaid_leave_days'] = merged_df['unpaid_leave_days'].fillna(0).astype(int)

            # Drop merge artifacts
            result_df = merged_df.drop(columns=['employee__registration_number'], errors='ignore')
            logger.debug("Leave merge completed successfully")
            return result_df

        except Exception as e:
            logger.error(f"Failed to merge leave records: {str(e)}", exc_info=True)
            raise


    def _merge_with_native_attendance(self, df: pd.DataFrame) -> pd.DataFrame:
        """Merge with internal attendance records."""
        logger.info("Merging with native attendance records")
        try:
            if df.empty:
                logger.warning("Empty employee DataFrame, skipping native attendance merge")
                return df

            attendances = (
                Attendance.objects.filter(
                    checked_at__date__range=(self.payroll.start_dt, self.payroll.end_dt),
                    count__gte=2
                ).filter(
                    sub_organization=self.payroll.sub_organization
                ).attended().values("employee__registration_number")
                .annotate(attendance=models.Count("employee__registration_number"))
            )

            if not attendances:
                logger.warning("No attendance records found for the date range")
                return df

            attendance_df = pd.DataFrame.from_records(attendances)
            logger.debug(f"Loaded {len(attendance_df)} attendance records")
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

            result_df = merged_df.drop(
                columns=["attendance_y", "attendance_x", "employee__registration_number"],
                errors="ignore",
            )
            logger.debug("Native attendance merge completed")
            return result_df
        except Exception as e:
            logger.error(f"Failed to merge native attendance: {str(e)}", exc_info=True)
            raise

    def _merge_with_canvas_attendance(self, df: pd.DataFrame) -> pd.DataFrame:
        """Merge with external attendance Excel file."""
        logger.info("Merging with canvas attendance records")
        if not self.payroll.canvas:
            logger.info("No canvas attendance data provided, skipping merge")
            return df

        canvas_url = getattr(self.payroll.canvas, "url", None)
        if not canvas_url:
            logger.warning("Canvas URL is None, skipping merge")
            return df

        try:
            file_path = self._resolve_file_path(canvas_url)
            
            if not os.path.exists(file_path):
                logger.warning(f"Canvas attendance file not found: {file_path}")
                return df

            canvas_df = pd.read_excel(file_path, dtype={"registration_number": str})
            if canvas_df.empty:
                logger.warning("Canvas attendance file is empty")
                return df

            logger.debug(f"Loaded canvas attendance with {len(canvas_df)} records")
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
            result_df = df.drop(columns=["absence", canvas_df.columns[0]], errors="ignore")
            logger.debug("Canvas attendance merge completed")
            return result_df
        except Exception as e:
            logger.error(f"Error reading canvas attendance: {str(e)}", exc_info=True)
            return df

    def _resolve_file_path(self, url: str) -> str:
        """Resolve URL or local path"""
        logger.debug(f"Resolving file path for URL: {url}")
        try:
            if validators.url(url):
                return url
            elif settings.DEBUG:
                resolved_path = os.path.join(os.getcwd(), url)
                logger.debug(f"Resolved local path: {resolved_path}")
                return resolved_path
            raise ValueError(f"Invalid canvas file path: {url}")
        except Exception as e:
            logger.error(f"Failed to resolve file path: {str(e)}", exc_info=True)
            raise

    def _save_paid_employees(self, df: pd.DataFrame):
        """Bulk create PaidEmployee entries from processed DataFrame."""
        logger.info("Saving paid employee records")
        try:
            if df.empty:
                logger.warning("No paid employee records to save")
                return

            paid_employees = [PaidEmployee(**{
                "sub_organization": getattr(self.payroll, "sub_organization", None),
                **record
            }) for record in df.to_dict("records")]
            logger.debug(f"Prepared {len(paid_employees)} paid employee records")
            PaidEmployee.objects.bulk_create(paid_employees)
            logger.info(f"Successfully saved {len(paid_employees)} paid employee records")
        except Exception as e:
            logger.error(f"Failed to save paid employees: {str(e)}", exc_info=True)
            raise