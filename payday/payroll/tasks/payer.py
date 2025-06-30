import pandas as pd
import numpy as np
import re

from django.conf import settings
from django.db.models import F, Sum
from core.models import fields
from django.db import models as django_model_fields
from django.apps import apps
from django.db import transaction
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional, Callable
from core.utils import DictToObject, set_schema
from logging import getLogger
from collections import defaultdict
from multiprocessing import Pool, cpu_count
from django.core.exceptions import ValidationError
from functools import lru_cache

logger = getLogger(__name__)

# Tax brackets
TRANCHE_RULES = [
    {"rate": 0.03, "range": (0, 162_000)},
    {"rate": 0.15, "range": (162_001, 1_800_000)},
    {"rate": 0.30, "range": (1_800_001, 3_600_000)},
    {"rate": 0.40, "range": (3_600_001, float("inf"))}
]

class DictToObject:
    """Convert a dictionary to an object with attribute and dictionary-like access."""
    def __init__(self, data: Dict):
        self._data = data
        for key, value in data.items():
            if isinstance(value, dict):
                setattr(self, key, DictToObject(value))
            else:
                setattr(self, key, value)

    def __getitem__(self, key):
        return self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __getattr__(self, key):
        return self._data[key]

class Payer:
    def __init__(self):
        self.errors = []
        self.now = datetime.now()
        self.today = self.now.date()
        self._model_cache = {}
        self.logger = logger

    @lru_cache(maxsize=128)
    def _get_model(self, app_label: str, model_name: str) -> Any:
        """Retrieve and cache Django model."""
        key = f"{app_label}.{model_name}"
        if key not in self._model_cache:
            try:
                self._model_cache[key] = apps.get_model(app_label, model_name)
            except LookupError as e:
                self.logger.error(f"Failed to load model {key}: {str(e)}", 
                                extra={'app_label': app_label, 'model_name': model_name})
                raise
        return self._model_cache[key]

    @transaction.atomic
    def run(self, schema: str, pk: int, *args, **kwargs) -> Dict[str, Any]:
        """Process payroll for given schema and payroll ID."""
        try:
            self._validate_inputs(schema, int(pk))
            
            if not getattr(settings, 'DEBUG', True):
                set_schema(schema)

            self._load_payroll(pk)
            if not self.payroll:
                raise ValidationError(f"Payroll {pk} not found")

            self._load_data()
            employee_values = self._prepare_employees_for_processing()
            worker_args = [(employee, self.special_items.get(employee["registration_number"], []))
                         for employee in employee_values]

            use_multiprocessing = not getattr(settings, 'DEBUG', False)
            results = self._process_employees(worker_args, use_multiprocessing)

            processed_employees, processed_items = [], []
            for emp, items in results:
                processed_employees.append(emp)
                processed_items.extend(items)

            self._save_processed_items(processed_items)
            self._save_processed_employees(processed_employees)

            PaidEmployee = self._get_model("payroll", "PaidEmployee")
            total_net = PaidEmployee.objects.filter(payroll=self.payroll).aggregate(
                Sum('net'))['net__sum'] or 0

            self.payroll.status = "COMPLETED"
            self.payroll.overall_net = total_net
            self.payroll.save(update_fields=["overall_net", "status"])

            self.logger.info(f"Payroll {pk} processed successfully", 
                           extra={'schema': schema, 'employee_count': len(processed_employees), 
                                  'item_count': len(processed_items)})
            return {
                "result": "success",
                "employees": len(processed_employees),
                "items": len(processed_items)
            }

        except Exception as e:
            self.logger.error(f"Error in Payer.run({schema}, {pk}): {str(e)}", 
                            extra={'schema': schema, 'payroll_id': pk}, 
                            exc_info=True)
            self._mark_payroll_error(pk, str(e))
            raise

    def _validate_inputs(self, schema: str, pk: int) -> None:
        """Validate input parameters."""
        if not isinstance(schema, str) or not schema.strip():
            raise ValidationError("Invalid schema name")
        if not isinstance(pk, int) or pk <= 0:
            raise ValidationError("Invalid payroll ID")

    def _process_employees(self, worker_args: List[Tuple], use_multiprocessing: bool) -> List[Tuple]:
        """Process employees either sequentially or in parallel."""
        shared_data = self._get_shared_data()
        pool_size = getattr(settings, "PAYROLL_WORKERS", min(cpu_count(), 4))

        if use_multiprocessing:
            with Pool(pool_size, initializer=self._init_worker, initargs=(shared_data,)) as pool:
                return pool.map(process_employee_worker, worker_args)
        return [process_employee_worker(args) for args in worker_args]

    def _init_worker(self, shared_data: Dict):
        """Initialize worker process with shared data."""
        global _SHARED_DATA
        _SHARED_DATA = shared_data

    def _get_shared_data(self) -> Dict[str, Any]:
        """Returns data needed by worker functions."""
        return {
            "items": self.items,
            "legal_items": self.legal_items,
            "payroll": self.payroll,
            "advancesalary": self.advancesalary,
            "special_items": self.special_items,
            "grade": self.grade,
            "status": self.status,
            "branch": self.branch,
            "agreement": self.agreement,
            "direction": self.direction,
            "subdirection": self.subdirection,
            "service": self.service,
            "designation": self.designation,
        }

    def _load_payroll(self, pk: int):
        """Load payroll data."""
        Payroll = self._get_model("payroll", "Payroll")
        try:
            self.payroll = Payroll.objects.select_related().get(id=pk)
            self.logger.debug(f"Loaded payroll {pk}", extra={'payroll_id': pk})
        except Payroll.DoesNotExist:
            self.logger.error(f"Payroll with id={pk} does not exist", extra={'payroll_id': pk})
            self.payroll = None
            raise

    def clean_metadata_keys(self, metadata: Dict) -> Dict:
        """Sanitize metadata keys."""
        return {re.sub(r'[^a-zA-Z0-9_]', '_', key.lower()): value 
                for key, value in metadata.items()}

    def _load_data(self):
        """Load required data for payroll processing."""
        Item = self._get_model("payroll", "Item")
        LegalItem = self._get_model("payroll", "LegalItem")
        SpecialEmployeeItem = self._get_model("payroll", "SpecialEmployeeItem")
        AdvanceSalaryPayment = self._get_model("payroll", "AdvanceSalaryPayment")

        self.items = list(Item.objects.filter(is_actif=True).values())
        self.legal_items = list(LegalItem.objects.filter(is_actif=True).values())

        # Validate data types for items and legal_items
        for item in self.items + self.legal_items:
            for field in ["formula_qp_employee", "formula_qp_employer", "condition"]:
                if not isinstance(item.get(field, ""), str):
                    self.logger.warning(f"Invalid {field} type for item {item.get('code', 'unknown')}: "
                                      f"expected string, got {type(item.get(field))}",
                                      extra={'item_code': item.get('code', 'unknown')})
                    item[field] = "0" if "formula" in field else "True"
            if not isinstance(item.get("is_bonus", False), bool):
                item["is_bonus"] = item.get("is_bonus", 0) == 1

        self.logger.debug(f"Loaded {len(self.items)} items and {len(self.legal_items)} legal items")

        special_items_qs = (
            SpecialEmployeeItem.objects.filter(end_date__gte=self.today)
            .select_related('item')
            .annotate(
                code=F("item__code"),
                name=F("item__name"),
                formula_qp_employee=F("amount_qp_employee"),
                formula_qp_employer=F("amount_qp_employer"),
            )
            .values("code", "name", "formula_qp_employee", "formula_qp_employer", "employee")
        )

        self.special_items = defaultdict(list)
        for item in special_items_qs:
            for field in ["formula_qp_employee", "formula_qp_employer"]:
                if not isinstance(item.get(field, ""), str):
                    self.logger.warning(f"Invalid {field} type for special item {item.get('code', 'unknown')}: "
                                      f"expected string, got {type(item.get(field))}",
                                      extra={'item_code': item.get('code', 'unknown'), 'employee': item['employee']})
                    item[field] = "0"
            self.special_items[item["employee"]].append(item)
        self.logger.debug(f"Loaded special items for {len(self.special_items)} employees")

        for model_name in ["grade", "status", "branch", "agreement", "direction", 
                         "subdirection", "service", "designation"]:
            model = self._get_model("employee", model_name)
            data = {
                str(g["id"]): self.clean_metadata_keys({**g["_metadata"], **dict(g)})
                for g in model.objects.values()
            }
            setattr(self, model_name, data)
            self.logger.debug(f"Loaded {len(data)} {model_name} records")

        advance_qs = (
            AdvanceSalaryPayment.objects.filter(
                date__range=[self.payroll.start_dt, self.payroll.end_dt])
            .values("advance_salary__employee__registration_number")
            .annotate(amount=Sum("amount"))
        )

        self.advancesalary = {
            item["advance_salary__employee__registration_number"]: item["amount"]
            for item in advance_qs
        }
        self.logger.debug(f"Loaded advance salary for {len(self.advancesalary)} employees")

    def _prepare_employees_for_processing(self):
        """Prepare employee data for processing."""
        PaidEmployee = self._get_model("payroll", "PaidEmployee")
        employees = list(
            PaidEmployee.objects.filter(payroll=self.payroll)
            .select_related("employee")
            .values()
        )
        self.logger.debug(f"Prepared {len(employees)} employees for processing")
        return employees

    def _save_processed_items(self, items: List[Dict]):
        """Save processed items in bulk."""
        if not items:
            self.logger.debug("No items to save")
            return
        ItemPaid = self._get_model("payroll", "ItemPaid")
        fields = {field.name for field in ItemPaid._meta.fields} - \
                {'id', '_metadata', 'updated_at', 'created_at'} | {'employee_id'}
        
        filtered_items = [
            {key: item[key] for key in item.keys() & fields} 
            for item in items
        ]
        ItemPaid.objects.bulk_create(
            [ItemPaid(**item) for item in filtered_items], 
            batch_size=1000, 
            ignore_conflicts=True
        )
        self.logger.debug(f"Saved {len(filtered_items)} processed items")

    def _save_processed_employees(self, employees: List[Dict]):
        """Save processed employee data in bulk."""
        if not employees:
            self.logger.debug("No employees to save")
            return
        PaidEmployee = self._get_model("payroll", "PaidEmployee")
        attrs = ["net", "gross", "taxable_gross", "social_security_threshold"]
        updates = [
            PaidEmployee(
                id=emp["id"],
                net=emp["net"],
                gross=emp["gross"],
                taxable_gross=emp["taxable_gross"],
                social_security_threshold=emp["social_security_threshold"]
            ) for emp in employees
        ]
        PaidEmployee.objects.bulk_update(updates, attrs, batch_size=1000)
        self.logger.debug(f"Saved {len(updates)} processed employees")

    def _mark_payroll_error(self, pk: int, message: str):
        """Mark payroll as errored with message."""
        Payroll = self._get_model("payroll", "Payroll")
        try:
            with transaction.atomic():
                payroll = Payroll.objects.get(pk=pk)
                payroll.status = "ERROR"
                errors = payroll.metadata.get("errors", [])
                errors.append({"message": message, "timestamp": self.now.isoformat()})
                payroll.metadata["errors"] = errors
                payroll.save(update_fields=["status", "metadata"])
                self.logger.debug(f"Marked payroll {pk} as ERROR", extra={'payroll_id': pk})
        except Exception as e:
            self.logger.error(f"Failed to mark payroll {pk} as ERROR: {str(e)}", 
                            extra={'payroll_id': pk})

def process_employee_worker(args: Tuple[Dict, List]) -> Tuple[Dict, List]:
    """Process a single employee's payroll data."""
    employee, special_items = args
    registration_number = employee["registration_number"]
    logger.debug(f"Processing employee {registration_number}")

    global _SHARED_DATA
    shared_data = _SHARED_DATA

    advancesalary = shared_data["advancesalary"]
    grade = shared_data["grade"]
    status = shared_data["status"]
    branch = shared_data["branch"]
    agreement = shared_data["agreement"]
    direction = shared_data["direction"]
    subdirection = shared_data["subdirection"]
    service = shared_data["service"]
    payroll = shared_data["payroll"]
    designation = shared_data["designation"]

    employee["advance_salary"] = advancesalary.get(registration_number, 0)

    for attr in ["grade", "status", "branch", "agreement", "direction", 
                "subdirection", "service", "designation"]:
        employee[attr] = shared_data.get(attr, {}).get(employee[attr], {})

    items_list = []
    context = {
        "payroll": payroll,
        "employee": DictToObject(employee),
        "itemspaid": pd.DataFrame(items_list) if items_list else pd.DataFrame()
    }

    all_items = shared_data["items"] + special_items + shared_data["legal_items"]
    df_items = pd.DataFrame(all_items)
    
    if df_items.empty:
        logger.debug(f"No items for employee {registration_number}")
        return employee, []

    def _eval(row):
        context["item"] = DictToObject(row.to_dict())
        try:
            expr = row.get("condition", "True")
            if not isinstance(expr, str):
                logger.warning(f"Invalid condition type for employee {registration_number}, "
                             f"item {row.get('code', 'unknown')}: expected string, got {type(expr)}",
                             extra={'employee_id': employee['id'], 'item_code': row.get('code', 'unknown')})
                return False
            return eval(expr, {"__builtins__": None}, context)
        except Exception as e:
            logger.warning(f"Condition evaluation failed for employee {registration_number}, "
                          f"item {row.get('code', 'unknown')}: {str(e)}",
                          extra={'employee_id': employee['id'], 'item_code': row.get('code', 'unknown')})
            return False

    df_items = df_items[df_items.apply(_eval, axis=1)]

    def safe_eval(expr, row):
        try:
            if not isinstance(expr, str):
                logger.warning(f"Invalid formula type for employee {registration_number}, "
                             f"item {row.get('code', 'unknown')}: expected string, got {type(expr)}",
                             extra={'employee_id': employee['id'], 'item_code': row.get('code', 'unknown')})
                return 0.0
            context["df_items"] = df_items
            context["ipr_iere"] = _ipr_iere_fast
            context["item"] = DictToObject(row.to_dict())
            context["sum_of_items_fields"] = sum_of_items_fields
            result = eval(expr, {"__builtins__": None}, context)
            return float(result) if isinstance(result, (int, float)) else 0.0
        except Exception as e:
            logger.warning(f"Formula evaluation failed for employee {registration_number}, "
                          f"item {row.get('code', 'unknown')}, formula '{expr}': {str(e)}",
                          extra={'employee_id': employee['id'], 'item_code': row.get('code', 'unknown')})
            return 0.0

    df_items["formula_qp_employee"].fillna("0", inplace=True)
    df_items["formula_qp_employer"].fillna("0", inplace=True)
    df_items["amount_qp_employee"] = df_items.apply(
        lambda row: safe_eval(row["formula_qp_employee"], row), axis=1)
    df_items["amount_qp_employer"] = df_items.apply(
        lambda row: safe_eval(row["formula_qp_employer"], row), axis=1)

    df_items["type_of_item"] = df_items["type_of_item"].fillna(1).astype(int)
    df_items["amount_qp_employee"] *= df_items["type_of_item"]
    df_items["time"] = df_items.apply(
        lambda row: safe_eval(row["time"] if isinstance(row["time"], str) else "0", row), axis=1)
    df_items["rate"] = np.where(df_items["time"] > 0, 
                              df_items["amount_qp_employee"] / df_items["time"], 0)

    df_items["is_social_security"] = df_items["is_social_security"].fillna(False)
    df_items["is_taxable"] = df_items["is_taxable"].fillna(False).astype(bool)
    df_items["is_payable"] = df_items["is_payable"].fillna(True).astype(bool)
    df_items["is_bonus"] = df_items["is_bonus"].fillna(False).astype(bool)

    # Initialize social_security_amount and taxable_amount
    df_items["social_security_amount"] = np.where(
        df_items["is_social_security"], df_items["amount_qp_employee"], 0)
    df_items["taxable_amount"] = np.where(
        df_items["is_taxable"], df_items["amount_qp_employee"], 0)
    df_items = df_items.replace([np.inf, -np.inf], 0).fillna(0)

    # Process legal items after initializing amounts
    for legal in shared_data["legal_items"]:
        code = legal["code"]
        filtered_df = df_items[df_items["code"] == code].copy()
        if filtered_df.empty:
            logger.debug(f"No data for legal item {code} for employee {registration_number}")
            continue
        filtered_df["amount_qp_employee"] = filtered_df.apply(
            lambda row: safe_eval(row["formula_qp_employee"], row), axis=1)
        filtered_df["amount_qp_employer"] = filtered_df.apply(
            lambda row: safe_eval(row["formula_qp_employer"], row), axis=1)
        df_items.update(filtered_df)

    employee["gross"] = df_items[df_items["is_payable"]]["amount_qp_employee"].sum()
    employee["social_security_threshold"] = df_items["social_security_amount"].sum()
    employee["taxable_gross"] = df_items["taxable_amount"].sum()
    employee["net"] = round(employee["gross"] - _ipr_iere_fast(df_items, employee), 2)

    excludable_fields = {"id", "_metadata", "updated_at", "created_at"}
    df_items["created_by"] = employee.get("created_by", None)
    df_items["updated_by"] = employee.get("updated_by", None)
    df_items["employee_id"] = employee.get("id", None)
    items_list = df_items.to_dict(orient="records")

    logger.debug(f"Completed processing for employee {registration_number}", 
                extra={'employee_id': employee['id']})
    return employee, items_list

def _ipr_iere_fast(df_items: pd.DataFrame, employee: dict) -> float:
    """Calculate tax efficiently."""
    df_items["is_bonus"] = df_items["is_bonus"].astype(bool)
    non_bonus_mask = ~df_items["is_bonus"]
    social_sec_threshold = df_items.loc[non_bonus_mask, "social_security_amount"].sum() * 0.05
    taxable_gross = df_items.loc[non_bonus_mask, "taxable_amount"].sum() - social_sec_threshold

    tax = 0
    for rule in TRANCHE_RULES:
        lower, upper = rule["range"]
        if lower <= taxable_gross <= upper:
            over_base = max(taxable_gross - lower, 0)
            base_tax = 4860
            tax = over_base * rule["rate"] + base_tax
            break

    bonus_tax = df_items.loc[df_items["is_bonus"], "taxable_amount"].sum() * 0.03
    tax += bonus_tax

    dependant_count = getattr(employee, "children", 0) + (
        1 if getattr(employee, "marital_status", 0) == "MARRIED" else 0
    )
    tax -= tax * (0.02 * dependant_count)
    return round(max(tax, 0), 2)

def sum_of_items_fields(df: pd.DataFrame, fields: str | List[str], 
                       condition: Optional[pd.Series] = None) -> float:
    """
    Sums specified fields in a DataFrame with an optional filtering condition.
    
    Parameters:
    - df (pd.DataFrame): The DataFrame to process
    - fields (str | list): A single column or list of columns to sum
    - condition (pd.Series | None): A filtering condition (e.g., df["is_payable"] == True)
    
    Returns:
    - float | int: The sum of selected fields, always returning a numeric value
    """
    if isinstance(fields, str):
        fields = [fields]
    
    valid_fields = [field for field in fields if field in df.columns]
    if not valid_fields:
        logger.debug(f"No valid fields found for summation: {fields}")
        return 0

    filtered_df = df[valid_fields]
    if condition is not None:
        filtered_df = df.loc[condition, valid_fields]
    
    result = float(filtered_df.sum().sum())
    logger.debug(f"Sum of fields {valid_fields}: {result}")
    return result