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

# Configure logger
logger = logging.getLogger(__name__)

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
        logger.debug(f"Initialized PayrollProcessor for payroll ID {payroll.id} with schema {schema}")

    def process(self):
        """Main entry point to start processing."""
        logger.info(f"Starting payroll processing for payroll ID {self.payroll.id}")
        start_time = time.time()
        try:
            self.statuses = ["en service"] #self.payroll.employee_status.all().values_list('name', flat=True).distinct()
            logger.debug(f"Retrieved {len(self.statuses)} employee statuses")
            df = self._get_employee_data()
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
        fields = [f.name for f in EmployeeModel._meta.fields if f.name not in self.exclude_fields]
        
        annotate_fields = {
            "working_days_per_month": models.functions.Coalesce(
                models.F("designation__working_days_per_month"), models.Value(23)
            ),
            "children": models.functions.Coalesce(models.Count("child"), models.Value(0)),
        }
    
        logger.debug(f"Building employee queryset with fields: {fields}")
        return (
            EmployeeModel.objects.filter(status__name__in=self.statuses)
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
            df["employee_id"] = df["registration_number"]
            df["payroll_id"] = self.payroll.id

            logger.debug("Employee data formatted successfully")
            return df
        except Exception as e:
            logger.error(f"Failed to load employee data: {str(e)}", exc_info=True)
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
                )
                .values("employee__registration_number")
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

            paid_employees = [PaidEmployee(**record) for record in df.to_dict("records")]
            logger.debug(f"Prepared {len(paid_employees)} paid employee records")
            PaidEmployee.objects.bulk_create(paid_employees)
            logger.info(f"Successfully saved {len(paid_employees)} paid employee records")
        except Exception as e:
            logger.error(f"Failed to save paid employees: {str(e)}", exc_info=True)
            raise