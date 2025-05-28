# payroll/tasks/payer.py

from django.conf import settings
from django.db.models import F, Sum
from django.apps import apps
from datetime import datetime
import pandas as pd
import itertools
from typing import Any, Dict, List, Tuple, Optional
from core.utils import DictToObject, set_schema
from logging import getLogger

from employee.models import *
from payroll.models import *

logger = getLogger(__name__)

class Payer:
    """
    A class-based processor that handles payroll computation synchronously or asynchronously,
    depending on DEBUG setting.
    
    Features:
      - Dynamic schema switching (multi-tenant)
      - Formula evaluation using restricted `eval`
      - Tax bracket logic (`ipr_iere`)
      - Bulk update for performance
    """

    # Tax brackets
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

    def run(self, schema: str, pk: int, *args, **kwargs) -> Dict[str, Any]:
        """Main entry point — runs sync or async based on DEBUG."""
        try:
            debug = getattr(settings, 'DEBUG', True)
            if not debug:
                set_schema(schema)
            self._load_payroll(pk)

            if not self.payroll:
                logger.error(f"Payroll {pk} not found.")
                raise ValueError(f"Payroll {pk} not found")

            self._load_data()
            employees, items_list = self._process_all_employees()
            self._save_processed_items(items_list)
            self._save_processed_employees(employees)

            self.payroll.status = "COMPLETED"
            self.payroll.save(update_fields=["status"])
            logger.info(f"Payroll {pk} processed successfully.")
            return {"result": "success", "employees": len(employees), "items": len(items_list)}

        except Exception as e:
            logger.error(f"Error in Payer.run({schema}, {pk}): {str(e)}", exc_info=True)
            self._mark_payroll_error(pk, str(e))
            raise

    def _load_payroll(self, pk: int):
        Payroll = apps.get_model("payroll", "Payroll")
        try:
            self.payroll = Payroll.objects.get(id=pk)
        except Payroll.DoesNotExist:
            logger.error(f"Payroll with id={pk} does not exist")
            self.payroll = None
            raise

    def _load_data(self):
        self.items = list(apps.get_model("payroll", "Item").objects.values())
        self.legal_items = list(apps.get_model("payroll", "LegalItem").objects.values())

        special_items_qs = (
            apps.get_model("payroll", "SpecialEmployeeItem")
            .objects.annotate(
                code=F("item__code"),
                name=F("item__name"),
                formula_qp_employee=F("amount_qp_employee"),
                formula_qp_employer=F("amount_qp_employer"),
            )
            .values("employee", "code", "name", "formula_qp_employee", "formula_qp_employer", "end_date")
        )

        df = pd.DataFrame(special_items_qs)
        self.special_items = (
            df.groupby("employee").apply(lambda x: x.to_dict(orient="records")).to_dict()
            if not df.empty else {}
        )

        grade_values = (
            apps.get_model("employee", "Grade")
            .objects.all()
            .values("name", "_metadata")
        )
        self.bareme = {g["name"]: g["_metadata"] for g in grade_values}

        advance_qs = (
            apps.get_model("payroll", "AdvanceSalaryPayment")
            .objects.filter(date__range=[self.payroll.start_dt, self.payroll.end_dt])
            .values("advance_salary__employee__registration_number")
            .annotate(amount=Sum("amount"))
        )

        self.advancesalary = {
            item["advance_salary__employee__registration_number"]: item["amount"]
            for item in advance_qs
        }

    def _process_all_employees(self) -> Tuple[List[Dict], List[Dict]]:
        PaidEmployee = apps.get_model("payroll", "PaidEmployee")
        employee_values = list(
            PaidEmployee.objects.filter(payroll=self.payroll)
            .select_related("employee")
            .values()
        )

        processed_employees = []
        processed_items = []

        for employee in employee_values:
            try:
                registration_number = employee["registration_number"]
                employee["advance_salary"] = self.advancesalary.get(registration_number, 0)
                employee["bareme"] = self.bareme.get(employee["grade"], {})
                special_items = self.special_items.get(registration_number, [])

                processed_employee, items = self.process_employee(employee, special_items)

                if processed_employee:
                    processed_employees.append(processed_employee)
                    processed_items.extend(items)

            except Exception as e:
                logger.warning(f"Error processing employee {employee['id']}: {e}")
                self.errors.append(str(e))

        return processed_employees, processed_items

    def _save_processed_items(self, items: List[Dict[str, Any]]):
        if not items:
            return

        ItemPaid = apps.get_model("payroll", "ItemPaid")
        valid_items = [item for item in items if item]
        ItemPaid.objects.bulk_create([ItemPaid(**item) for item in valid_items])

    def _save_processed_employees(self, employees: List[Dict]):
        if not employees:
            return

        attrs = ["net", "gross", "taxable_gross", "social_security_threshold"]
        ids = {emp["id"]: emp for emp in employees}
        objs = PaidEmployee.objects.filter(id__in=ids.keys())

        for obj in objs:
            for attr in attrs:
                setattr(obj, attr, ids[obj.id][attr])

        PaidEmployee.objects.bulk_update(objs, attrs)

    def process_employee(self, employee: dict, special_items: list) -> Tuple[Dict, List[Dict]]:
        items = []

        for item in self.items:
            _item = self.process_item(employee, items, item)
            if _item:
                items.append(_item)

        for item in special_items:
            _item = self.process_item(employee, items, item)
            if _item:
                items.append(_item)

        employee["gross"] = sum(item["amount_qp_employee"] for item in items if item.get("is_payable", True))
        
        for legal in self.legal_items:
            _item = self.process_item(employee, items, legal)
            if _item:
                items.append(_item)

        employee["social_security_threshold"] = sum(item["social_security_amount"] for item in items)
        employee["net"] = sum(item["amount_qp_employee"] for item in items if item.get("is_payable", True))
        employee["taxable_gross"] = sum(item["taxable_amount"] for item in items)

        return employee, items

    def process_item(self, employee: dict, itemspaid: list, item: dict) -> Optional[Dict]:
        condition = item.get("condition", "True")
        context = {
            "employee": DictToObject(employee),
            "item": DictToObject(item),
            "payroll": self.payroll,
            "self": self,
            "itemspaid": pd.DataFrame(itemspaid) if itemspaid else pd.DataFrame(),
        }

        try:
            condition_result = eval(condition, {"__builtins__": None}, context)
        except Exception as e:
            logger.warning(f"Condition failed for item {item['code']}: {e}")
            condition_result = False

        if not condition_result:
            return None

        formula_qp_employee = str(item.get('formula_qp_employee', '0'))
        formula_qp_employer = str(item.get('formula_qp_employer', '0'))
        time = item.get("time", str(employee.get("attendance", 0)))

        try:
            formula_qp_employee = self.evaluate(formula_qp_employee, context) or 0
            formula_qp_employer = self.evaluate(formula_qp_employer, context) or 0
            time = self.evaluate(time, context) or 0
        except Exception as e:
            logger.warning(f"Formula eval failed for {item.get('code')}: {e}")
            return None

        type_of_item = int(item.get("type_of_item", 1))
        amount_qp_employee = formula_qp_employee * type_of_item
        amount_qp_employer = formula_qp_employer
        social_security_amount = amount_qp_employee if item.get("is_social_security", False) else 0
        taxable_amount = amount_qp_employee if item.get("is_taxable", False) else 0
        rate = amount_qp_employee / time if time else 0

        return {
            "code": item["code"],
            "name": item["name"],
            "time": time,
            "rate": round(rate, 2),
            "employee_id": employee["id"],
            "type_of_item": type_of_item,
            "amount_qp_employer": amount_qp_employer,
            "amount_qp_employee": amount_qp_employee,
            "social_security_amount": social_security_amount,
            "taxable_amount": taxable_amount,
            "is_payable": item.get("is_payable", True),
            "is_bonus": item.get("is_bonus", False),
        }

    def evaluate(self, expr: str, context: dict) -> Optional[float]:
        try:
            result = eval(expr, {"__builtins__": None}, context)
            return float(result) if isinstance(result, (int, float)) else result
        except Exception as e:
            logger.warning(f"Evaluation error: {expr} → {e}")
            return None

    def get_tranche(self, taxable_gross: float):
        for rule in self.TRANCHE_RULES:
            lower, upper = rule["range"]
            if lower <= taxable_gross <= upper:
                return {"percentage": rule["rate"], "tranche": (lower, upper)}
        return {"percentage": 0.40, "tranche": (3_600_001, float("inf"))}

    def ipr_iere(self, payroll, employee, items, item) -> float:
        df = pd.DataFrame(items)
        df = df[df["is_payable"] == True]

        social_security_threshold = df.loc[df["is_bonus"] == False, "social_security_amount"].sum()
        taxable_gross = df.loc[df["is_bonus"] == False, "taxable_amount"].sum()

        social_security_threshold *= 0.05
        taxable_gross -= social_security_threshold
        tranche = self.get_tranche(taxable_gross)

        taxable_gross -= tranche["tranche"][0]
        taxable_gross *= tranche["rate"]
        taxable_gross += 4860

        bonus_df = df.loc[df["is_bonus"] == True, "taxable_amount"].sum()
        taxable_bonus = bonus_df * 0.03
        taxable_gross += taxable_bonus

        dependant_count = employee.get("children", 0) + (
            1 if employee.get("marital_status") == "MARRIED" else 0
        )
        dependant_adjustment = taxable_gross * (0.02 * dependant_count)
        taxable_gross -= dependant_adjustment

        return round(taxable_gross, 2)

    def _mark_payroll_error(self, pk: int, message: str):
        Payroll = apps.get_model("payroll", "Payroll")
        try:
            payroll = Payroll.objects.get(pk=pk)
            payroll.status = "ERROR"
            payroll.metadata["errors"] = payroll.metadata.get("errors", []) + [{"message": message}]
            payroll.save(update_fields=["status", "metadata"])
        except Exception as e:
            logger.error(f"Failed to mark payroll {pk} as ERROR: {e}")