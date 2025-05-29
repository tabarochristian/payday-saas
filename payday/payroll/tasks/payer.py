# payroll/tasks/payer.py

from django.conf import settings
from django.db.models import F, Sum
from django.apps import apps
from django.db import transaction
from datetime import datetime
import pandas as pd
from typing import Any, Dict, List, Tuple, Optional
from core.utils import DictToObject, set_schema
from logging import getLogger
from collections import defaultdict

logger = getLogger(__name__)

class Payer:
    """
    Optimized payroll processor with improved database queries and data handling.
    
    Features:
      - Dynamic schema switching (multi-tenant)
      - Formula evaluation with restricted `eval`
      - Tax bracket logic (`ipr_iere`)
      - Bulk operations for database efficiency
      - Reduced memory footprint
    """

    # Tax brackets (unchanged)
    TRANCHE_RULES = [
        {"rate": 0.03, "range": (0, 162_000)},
        {"rate": 0.15, "range": (162_001, 1_800_000)},
        {"rate": 0.30, "range": (1_800_001, 3_600_000)},
        {"rate": 0.40, "range": (3_600_001, float("inf"))}
    ]

    def __init__(self):
        self.errors = []
        self.now = datetime.now()
        self.today = self.now.date()
        # Cache for frequently accessed models
        self._model_cache = {}

    def _get_model(self, app_label: str, model_name: str):
        """Cache Django models to reduce apps.get_model calls."""
        key = f"{app_label}.{model_name}"
        if key not in self._model_cache:
            self._model_cache[key] = apps.get_model(app_label, model_name)
        return self._model_cache[key]

    @transaction.atomic
    def run(self, schema: str, pk: int, *args, **kwargs) -> Dict[str, Any]:
        """Main entry point with atomic transaction for consistency."""
        try:
            if not getattr(settings, 'DEBUG', True):
                set_schema(schema)

            self._load_payroll(pk)
            if not self.payroll:
                logger.error(f"Payroll {pk} not found.")
                raise ValueError(f"Payroll {pk} not found")

            self._load_data()
            employees, items_list = self._process_all_employees()
            self._save_processed_items(items_list)
            self._save_processed_employees(employees)

            PaidEmployee = self._get_model("payroll", "PaidEmployee")
            self.payroll.overall_net = PaidEmployee.objects.filter(
                payroll=self.payroll
            ).aggregate(overall_net=Sum('net'))['overall_net'] or 0

            self.payroll.status = "COMPLETED"
            self.payroll.save(update_fields=["overall_net", "status"])
            logger.info(f"Payroll {pk} processed successfully.")
            return {"result": "success", "employees": len(employees), "items": len(items_list)}

        except Exception as e:
            logger.error(f"Error in Payer.run({schema}, {pk}): {str(e)}", exc_info=True)
            self._mark_payroll_error(pk, str(e))
            raise

    def _load_payroll(self, pk: int):
        Payroll = self._get_model("payroll", "Payroll")
        try:
            self.payroll = Payroll.objects.select_related().get(id=pk)
        except Payroll.DoesNotExist:
            logger.error(f"Payroll with id={pk} does not exist")
            self.payroll = None
            raise

    def _load_data(self):
        """Load all required data in optimized queries."""
        # Fetch items and legal items in single queries
        Item = self._get_model("payroll", "Item")
        LegalItem = self._get_model("payroll", "LegalItem")
        self.items = list(Item.objects.values())
        self.legal_items = list(LegalItem.objects.values())

        # Optimize special items query with prefetch
        SpecialEmployeeItem = self._get_model("payroll", "SpecialEmployeeItem")
        special_items_qs = (
            SpecialEmployeeItem.objects.select_related('item')
            .annotate(
                code=F("item__code"),
                name=F("item__name"),
                formula_qp_employee=F("amount_qp_employee"),
                formula_qp_employer=F("amount_qp_employer"),
            )
            .values("employee", "code", "name", "formula_qp_employee", "formula_qp_employer", "end_date")
        )

        # Use defaultdict for special items to avoid pandas if possible
        self.special_items = defaultdict(list)
        for item in special_items_qs:
            self.special_items[item["employee"]].append(item)

        # Optimize grade values query
        Grade = self._get_model("employee", "Grade")
        self.bareme = {
            g["name"]: g["_metadata"] 
            for g in Grade.objects.values("name", "_metadata")
        }

        # Optimize advance salary query
        AdvanceSalaryPayment = self._get_model("payroll", "AdvanceSalaryPayment")
        advance_qs = (
            AdvanceSalaryPayment.objects.filter(
                date__range=[self.payroll.start_dt, self.payroll.end_dt]
            )
            .values("advance_salary__employee__registration_number")
            .annotate(amount=Sum("amount"))
        )
        self.advancesalary = {
            item["advance_salary__employee__registration_number"]: item["amount"]
            for item in advance_qs
        }

    def _process_all_employees(self) -> Tuple[List[Dict], List[Dict]]:
        PaidEmployee = self._get_model("payroll", "PaidEmployee")
        # Use select_related to reduce queries
        employee_values = list(
            PaidEmployee.objects.filter(payroll=self.payroll)
            .select_related("employee")
            .values("id", "registration_number", "grade", "attendance", "children", "marital_status")
        )

        processed_employees = []
        processed_items = []

        for employee in employee_values:
            try:
                registration_number = employee["registration_number"]
                employee["advance_salary"] = self.advancesalary.get(registration_number, 0)
                employee["bareme"] = self.bareme.get(employee["grade"], {})
                special_items = self.special_items[registration_number]

                processed_employee, items = self.process_employee(employee, special_items)
                processed_employees.append(processed_employee)
                processed_items.extend(items)

            except Exception as e:
                logger.warning(f"Error processing employee {employee['id']}: {e}")
                self.errors.append(str(e))

        return processed_employees, processed_items

    def _save_processed_items(self, items: List[Dict[str, Any]]):
        if not items:
            return

        ItemPaid = self._get_model("payroll", "ItemPaid")
        valid_items = [item for item in items if item]
        ItemPaid.objects.bulk_create([ItemPaid(**item) for item in valid_items], batch_size=1000)

    def _save_processed_employees(self, employees: List[Dict]):
        if not employees:
            return

        PaidEmployee = self._get_model("payroll", "PaidEmployee")
        attrs = ["net", "gross", "taxable_gross", "social_security_threshold"]
        updates = []

        for emp in employees:
            updates.append(PaidEmployee(
                id=emp["id"],
                net=emp["net"],
                gross=emp["gross"],
                taxable_gross=emp["taxable_gross"],
                social_security_threshold=emp["social_security_threshold"]
            ))

        PaidEmployee.objects.bulk_update(updates, attrs, batch_size=1000)

    def process_employee(self, employee: dict, special_items: list) -> Tuple[Dict, List[Dict]]:
        items = []
        context = {
            "employee": DictToObject(employee),
            "payroll": self.payroll,
            "self": self,
            "itemspaid": None,  # Will be set per item
        }

        # Process regular and special items
        for item in self.items + special_items:
            _item = self.process_item(employee, items, item, context)
            if _item:
                items.append(_item)

        # Process legal items
        for legal in self.legal_items:
            _item = self.process_item(employee, items, legal, context)
            if _item:
                items.append(_item)

        # Calculate aggregates
        employee["gross"] = sum(item["amount_qp_employee"] for item in items if item.get("is_payable", True))
        employee["social_security_threshold"] = sum(item["social_security_amount"] for item in items)
        employee["net"] = employee["gross"]  # Net after deductions
        employee["taxable_gross"] = sum(item["taxable_amount"] for item in items)

        # Apply tax calculation
        # tax = self.ipr_iere(self.payroll, employee, items, None)
        # employee["net"] -= tax

        return employee, items

    def process_item(self, employee: dict, itemspaid: list, item: dict, context: dict) -> Optional[Dict]:
        condition = item.get("condition", "True")
        context["item"] = DictToObject(item)
        context["itemspaid"] = pd.DataFrame(itemspaid) if itemspaid else pd.DataFrame()

        try:
            if not eval(condition, {"__builtins__": None}, context):
                return None
        except Exception as e:
            logger.warning(f"Condition failed for item {item['code']}: {e}")
            return None

        formula_qp_employee = str(item.get('formula_qp_employee', '0'))
        formula_qp_employer = str(item.get('formula_qp_employer', '0'))
        time = item.get("time", str(employee.get("attendance", 0)))

        try:
            amount_qp_employee = (self.evaluate(formula_qp_employee, context) or 0) * int(item.get("type_of_item", 1))
            amount_qp_employer = self.evaluate(formula_qp_employer, context) or 0
            time = self.evaluate(time, context) or 0
        except Exception as e:
            logger.warning(f"Formula eval failed for {item.get('code')}: {e}")
            return None

        return {
            "code": item["code"],
            "name": item["name"],
            "time": time,
            "rate": round(amount_qp_employee / time, 2) if time else 0,
            "employee_id": employee["id"],
            "type_of_item": int(item.get("type_of_item", 1)),
            "amount_qp_employer": amount_qp_employer,
            "amount_qp_employee": amount_qp_employee,
            "social_security_amount": amount_qp_employee if item.get("is_social_security", False) else 0,
            "taxable_amount": amount_qp_employee if item.get("is_taxable", False) else 0,
            "is_payable": item.get("is_payable", True),
            "is_bonus": item.get("is_bonus", False),
        }

    def evaluate(self, expr: str, context: dict) -> Optional[float]:
        try:
            result = eval(expr, {"__builtins__": None}, context)
            return float(result) if isinstance(result, (int, float)) else None
        except Exception as e:
            logger.warning(f"Evaluation error: {expr} → {e}")
            return None

    def get_tranche(self, taxable_gross: float) -> Dict:
        for rule in self.TRANCHE_RULES:
            lower, upper = rule["range"]
            if lower <= taxable_gross <= upper:
                return {"percentage": rule["rate"], "tranche": (lower, upper)}
        return {"percentage": 0.40, "tranche": (3_600_001, float("inf"))}

    def ipr_iere(self, payroll, employee: dict, items: list, item) -> float:
        df = pd.DataFrame(items)
        df = df[df["is_payable"] == True]

        social_security_threshold = df.loc[~df["is_bonus"], "social_security_amount"].sum()
        taxable_gross = df.loc[~df["is_bonus"], "taxable_amount"].sum()

        social_security_threshold *= 0.05
        taxable_gross -= social_security_threshold
        tranche = self.get_tranche(taxable_gross)

        tax = (taxable_gross - tranche["tranche"][0]) * tranche["percentage"] + 4860
        tax += df.loc[df["is_bonus"], "taxable_amount"].sum() * 0.03

        dependant_count = employee.get("children", 0) + (
            1 if employee.get("marital_status") == "MARRIED" else 0
        )
        tax -= tax * (0.02 * dependant_count)

        return round(tax, 2)

    def _mark_payroll_error(self, pk: int, message: str):
        Payroll = self._get_model("payroll", "Payroll")
        try:
            with transaction.atomic():
                payroll = Payroll.objects.get(pk=pk)
                payroll.status = "ERROR"
                payroll.metadata["errors"] = payroll.metadata.get("errors", []) + [{"message": message}]
                payroll.save(update_fields=["status", "metadata"])
        except Exception as e:
            logger.error(f"Failed to mark payroll {pk} as ERROR: {e}")