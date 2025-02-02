from django.shortcuts import get_object_or_404
from django.conf import settings

from core.models import Notification
from employee.models import *
from payroll.models import *
from django.db import models


from datetime import datetime
from payday.celery import app
from celery import Task
import pandas as pd
import itertools
import os

from core.utils import DictToObject

class Payer(Task):
    """
    Celery Task to handle payroll processing and payslip generation.
    """
    errors = []
    name = 'payer'
    DEBUG = settings.DEBUG
    WORKERS = os.cpu_count() * (1.0 if DEBUG else 1.5)

    TRANCHES = {
        0.03: [0, 162000],
        0.15: [162001, 1800000],
        0.30: [1800001, 3600000],
        0.40: [3600001, 9999999999999]
    }

    def run(self, pk: int, *args, **kwargs) -> None:
        """
        Main entry point for the task. Processes the payroll.
        
        Args:
            pk (int): Primary key of the payroll to process.
        """
        self.now = datetime.now()
        self.today = self.now.today
        self.payroll = get_object_or_404(Payroll, pk=pk)

        self.items = list(Item.objects.all().values())
        self.legal_items = list(LegalItem.objects.all().values())

        self.employees = PaidEmployee.objects.filter(payroll=self.payroll)
        self.employees = self.employees.select_related('employee').values()
        self.employees = list(self.employees.values())
        
        self.bareme = Grade.objects.all().values('name', '_metadata')
        self.bareme = {g['name']: g['_metadata'] for g in self.bareme}

        self.advancesalary = AdvanceSalaryPayment.objects.filter(
            date__range=[self.payroll.start_dt, self.payroll.end_dt]
        ).values('advance_salary__employee__registration_number').annotate(
            amount=models.Sum('amount')
        )
        self.advancesalary = {
            a['advance_salary__employee__registration_number']: a['amount'] for a in self.advancesalary
        }

        self.process()
        
        self.payroll.status = 'COMPLETED'
        self.payroll.update()

        print(f'Payroll {self.payroll} processed successfully.')

    def process(self) -> None:
        """Process all employees and their items."""
        employees, items = [], []

        for employee in self.employees:
            employee['advance_salary'] = self.advancesalary.get(employee['registration_number'], 0)
            employee['bareme'] = self.bareme.get(employee['grade'], {})
            
            employee, _items = self.process_employee(employee)
            employees.append(employee)
            items.append(_items)

        self.save_items(items)
        self.save_employees(employees)

    def save_items(self, items: list) -> None:
        """
        Save the items to the database.
        
        Args:
            items (List[Dict[str, Any]]): List of items to save.
        """
        items = list(itertools.chain.from_iterable(items))
        items = [ItemPaid(**item) for item in items]
        ItemPaid.objects.bulk_create(items)

    def save_employees(self, employees: list) -> None:
        """
        Save the employees to the database.
        
        Args:
            employees (List[Dict[str, Any]]): List of employees to save.
        """
        attrs = ['net', 'gross', 'taxable_gross', 'social_security_threshold']
        ids = {employee['id']: employee for employee in employees}
        objs = PaidEmployee.objects.filter(id__in=ids.keys())
        
        for obj in objs:
            for attr in attrs:
                value = ids[obj.id][attr]
                setattr(obj, attr, value)

        PaidEmployee.objects.bulk_update(objs, attrs)

    def process_employee(self, employee: dict) -> tuple:
        """
        Process the payroll for a single employee.
        
        Args:
            employee (Dict[str, Any]): Employee data to process.
        
        Returns:
            Tuple[Dict[str, Any], List[Dict[str, Any]]]: Processed employee data and items.
        """
        items = []
        
        for item in self.items:
            _item = self.process_item(employee, items, item)
            if _item:
                items.append(_item)

        employee['gross'] = sum([item['amount_qp_employee'] for item in items if item['is_payable']])

        for legal in self.legal_items:
            _item = self.process_item(employee, items, legal)
            if _item:
                items.append(_item)

        employee['social_security_threshold'] = sum([item['social_security_amount'] for item in items])
        employee['net'] = sum([item['amount_qp_employee'] for item in items if item['is_payable']])
        employee['taxable_gross'] = sum([item['taxable_amount'] for item in items])
        
        return employee, items

    def process_item(self, employee: dict, itemspaid: list, item: dict) -> dict:
        """
        Process a single item for an employee.
        
        Args:
            employee (Dict[str, Any]): Employee data.
            item (Dict[str, Any]): Item data.
        
        Returns:
            Optional[Dict[str, Any]]: Processed item data or None if the condition is not met.
        """
        condition = item.get('condition', 'False')
        context = {
            'itemspaid': pd.DataFrame(itemspaid),
            'employee': DictToObject(employee),
            'item': DictToObject(item),
            'payroll': self.payroll,
            'self': self,
        }

        condition = self.evaluate_expression(condition, context)

        if not condition:
            return None
        
        formula_qp_employee = item.get('formula_qp_employee', '0')
        formula_qp_employer = item.get('formula_qp_employer', '0')
        time = item.get('time', str(employee['attendance']))

        formula_qp_employee = self.evaluate_expression(formula_qp_employee, context) or 0
        formula_qp_employer = self.evaluate_expression(formula_qp_employer, context) or 0
        time = self.evaluate_expression(time, context) or 0

        type_of_item = int(item.get('type_of_item', '1'))
        formula_qp_employee = formula_qp_employee * type_of_item

        social_security_amount = formula_qp_employee if item.get('is_social_security') else 0
        taxable_amount = formula_qp_employee if item.get('is_taxable') else 0
        rate = (formula_qp_employee / time) if time else 0

        is_payable = item.get('is_payable', True)
        is_bonus = item.get('is_bonus', False)

        return {
            'code': item['code'],
            'name': item['name'],
            
            'time': time,
            'rate': rate,

            'employee_id': employee['id'],
            'type_of_item': type_of_item,

            'amount_qp_employer': formula_qp_employer,
            'amount_qp_employee': formula_qp_employee,

            'social_security_amount': social_security_amount,
            'taxable_amount': taxable_amount,
            
            'is_payable': is_payable,
            'is_bonus': is_bonus
        }

    def evaluate_expression(self, expression: str, context: dict):
        """
        Safely evaluate an expression using the provided context.
        
        Args:
            expression (str): The expression to evaluate.
            context (Dict[str, Any]): The context for evaluation.
        
        Returns:
            Any: The result of the evaluation.
        """
        try:
            return eval(expression, {"__builtins__": None}, context)
        except Exception as e:
            self.errors.append(str(e))
            return None

    def get_tranche(self, taxable_gross):
        for percentage, (lower_bound, upper_bound) in self.TRANCHES.items():
            if lower_bound <= taxable_gross <= upper_bound:
                return {'percentage': percentage, 'tranche': (lower_bound, upper_bound)}
        return None

    def ipr_iere(self, payroll, employee, items, item):
        items = items[items['is_payable'] == True]

        social_security_threshold = items.loc[(items['is_bonus'] == False), 'social_security_amount'].sum()
        taxable_gross = items.loc[(items['is_bonus'] == False), 'taxable_amount'].sum()

        social_security_threshold = social_security_threshold * 0.05
        taxable_amount = taxable_gross - social_security_threshold
        tranche = self.get_tranche(taxable_amount)

        taxable_amount -= tranche['tranche'][0]
        taxable_amount *= tranche['percentage']
        taxable_amount += 4860
        
        taxable_bonus = items.loc[(items['is_bonus'] == True), 'taxable_amount'].sum()
        taxable_bonus = taxable_bonus * 0.03
        
        taxable_amount = taxable_amount + taxable_bonus

        dependant = employee.children + (1 if employee.marital_status == 'MARRIED' else 0)
        dependant = taxable_amount * (0.02 * dependant)
        taxable_amount -= dependant

        return round(taxable_amount, 2)


app.register_task(Payer())
