import random
import logging
from faker import Faker
from django.apps import apps
from django.core.management.base import BaseCommand
from django.db.utils import IntegrityError
from django.conf import settings
from typing import List, Any
from dataclasses import dataclass
from functools import lru_cache
from core.utils import set_schema

# -----------------------------------
# Configuration
# -----------------------------------

@dataclass
class Config:
    LOG_FILE: str = "seed.log"
    LOG_LEVEL: str = getattr(settings, 'LOGGING', {}).get('level', 'INFO')
    NUM_EMPLOYEES: int = 50
    BATCH_SIZE: int = 100
    FAKER_LOCALE: str = "fr_FR"

CONFIG = Config()

def setup_logger():
    logger = logging.getLogger("seeder")
    logger.setLevel(CONFIG.LOG_LEVEL)

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")

    file_handler = logging.FileHandler(CONFIG.LOG_FILE)
    file_handler.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(file_handler)

    return logger

logger = setup_logger()
fake = Faker(CONFIG.FAKER_LOCALE)

# -----------------------------------
# Management Command
# -----------------------------------

class Command(BaseCommand):
    help = "Generate fake data dynamically for models in a specified app"

    def add_arguments(self, parser):
        parser.add_argument('schema', type=str, help='The schema name (subdomain) for the tenant')
        parser.add_argument('--suborganization', type=str, help='The sub-organization name', default=None)

    def handle(self, *args, **kwargs):
        self.schema = kwargs['schema'].lower()
        self.suborganization = (kwargs['suborganization'] or 'default').lower()

        if not getattr(settings, 'DEBUG', True):
            set_schema(self.schema)

        try:
            logger.info("Starting data seeding", extra=self.log_context())

            grades = self.get_or_create_fake_grade()
            statuses = self.get_or_create_status()
            branches = self.get_or_create_branch()
            agreements = self.get_or_create_agreement()
            directions = self.get_or_create_direction()
            designations = self.get_or_create_designation()
            employees = self.get_or_create_employee(grades, statuses, branches, agreements, directions, designations)
            leaves = self.get_or_create_leave_type()
            legal_items = self.get_or_create_legal_payslip_element()
            payslip_items = self.get_or_create_payslip_element(grades)

            logger.info("Seeding completed", extra=self.log_context())

        except Exception as e:
            logger.error(f"Seeding failed: {e}", exc_info=True, extra=self.log_context())
            raise

    def log_context(self):
        return {
            'schema': self.schema,
            'suborganization': self.suborganization
        }

    def get_or_create_objects(self, app_label: str, model_name: str, instances: List[Any], label: str) -> List[Any]:
        model = self._get_model(app_label, model_name)
        existing = list(model.objects.all())
        if existing:
            logger.info(f"Returning existing {label}", extra=self.log_context() | {'model': model_name})
            return existing
        try:
            model.objects.bulk_create(instances, batch_size=CONFIG.BATCH_SIZE)
            logger.info(f"Created {len(instances)} {label}", extra=self.log_context() | {'model': model_name})
        except IntegrityError as e:
            logger.error(f"Failed to create {label}: {e}", exc_info=True, extra=self.log_context() | {'model': model_name})
            raise
        return list(model.objects.all())

    @lru_cache(maxsize=32)
    def _get_model(self, app_label: str, model_name: str) -> Any:
        try:
            return apps.get_model(app_label, model_name)
        except LookupError as e:
            logger.error(f"Model '{model_name}' not found in '{app_label}': {e}", extra=self.log_context())
            raise

    # -----------------------------
    # Entity Creation Methods
    # -----------------------------

    def get_or_create_fake_grade(self):
        model = self._get_model('employee', 'Grade')
        grades = ["directeur", "manager", "collaborateur", "subalterne"]

        def compute_value(base, index): return base * ((4 - index) / 10) if index > 0 else base

        instances = [
            model(
                name=grade,
                group=grade.upper(),
                sub_organization=self.suborganization,
                _metadata={
                    "base": compute_value(2_000_000, i),
                    "transport": compute_value(200_000, i),
                    "logement": compute_value(400_000, i),
                    "prime_ind": compute_value(250_000, i),
                    "all_fam": compute_value(150_000, i)
                }
            ) for i, grade in enumerate(grades)
        ]
        return self.get_or_create_objects('employee', 'Grade', instances, 'grades')

    def get_or_create_status(self):
        model = self._get_model('employee', 'Status')
        status_list = [
            ("ACTIF", "en service", True),
            ("ACTIF", "en congé", True),
            ("INACTIF", "en suspension", False),
            ("ACTIF", "en mission", True),
            ("INACTIF", "retiré", False),
        ]
        instances = [
            model(
                name=name,
                group=group,
                _metadata={"est_actif": is_active},
                sub_organization=self.suborganization
            ) for group, name, is_active in status_list
        ]
        return self.get_or_create_objects('employee', 'Status', instances, 'statuses')

    def get_or_create_branch(self):
        model = self._get_model('employee', 'Branch')
        branches = [
            ("Kinshasa", 5000),
            ("Lubumbashi", 4500),
            ("Goma", 6000),
            ("Kisangani", 4000),
            ("Matadi", 3500)
        ]
        instances = [
            model(
                name=name,
                _metadata={"taxi_price": price, "fuel_price": price},
                sub_organization=self.suborganization
            ) for name, price in branches
        ]
        return self.get_or_create_objects('employee', 'Branch', instances, 'branches')

    def get_or_create_agreement(self):
        model = self._get_model('employee', 'Agreement')
        agreements = [
            ("CDI", {"durée": "indéterminée", "renouvelable": False}),
            ("CDD", {"durée": "12 mois", "renouvelable": True}),
            ("Stage", {"durée": "6 mois", "renouvelable": False}),
            ("Freelance", {"durée": "projet", "renouvelable": True}),
            ("Consultant", {"durée": "contrat", "renouvelable": True}),
        ]
        instances = [
            model(name=name, _metadata=meta, sub_organization=self.suborganization)
            for name, meta in agreements
        ]
        return self.get_or_create_objects('employee', 'Agreement', instances, 'agreements')

    def get_or_create_direction(self):
        model = self._get_model('employee', 'Direction')
        directions = [
            ("Direction Générale", {"responsable": "PDG", "budget_annuel": "10M CDF"}),
            ("RH", {"responsable": "Directeur RH", "budget_annuel": "2M CDF"}),
            ("Finance", {"responsable": "DAF", "budget_annuel": "5M CDF"}),
            ("Informatique", {"responsable": "CTO", "budget_annuel": "3M CDF"}),
            ("Commercial", {"responsable": "Directeur Commercial", "budget_annuel": "4M CDF"}),
        ]
        instances = [
            model(name=name, _metadata=meta, sub_organization=self.suborganization)
            for name, meta in directions
        ]
        return self.get_or_create_objects('employee', 'Direction', instances, 'directions')

    def get_or_create_designation(self):
        model = self._get_model('employee', 'Designation')
        designations = [
            ("Directeur Général", {"niveau": "Exécutif"}),
            ("Responsable RH", {"niveau": "Cadre"}),
            ("DAF", {"niveau": "Cadre supérieur"}),
            ("Ingénieur", {"niveau": "Intermédiaire"}),
            ("Commercial", {"niveau": "Expérimenté"}),
        ]
        instances = [
            model(name=name, _metadata=meta, sub_organization=self.suborganization)
            for name, meta in designations
        ]
        return self.get_or_create_objects('employee', 'Designation', instances, 'designations')

    def get_or_create_employee(self, grades, statuses, branches, agreements, directions, designations):
        model = self._get_model('employee', 'Employee')
        instances = [
            model(
                social_security_number=fake.ssn(),
                registration_number=fake.unique.random_number(digits=8),
                middle_name=fake.first_name(),
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                gender=random.choice(["MALE", "FEMALE"]),
                email=fake.email(),
                physical_address=fake.address().replace('\n', ', '),
                mobile_number=fake.phone_number(),
                grade=random.choice(grades),
                status=random.choice(statuses),
                branch=random.choice(branches),
                agreement=random.choice(agreements),
                direction=random.choice(directions),
                designation=random.choice(designations),
                date_of_join=fake.date_between(start_date="-5y", end_date="today"),
                date_of_birth=fake.date_of_birth(minimum_age=18, maximum_age=65),
                sub_organization=self.suborganization,
                payment_account=fake.iban(),
                payment_method=random.choice(["CASH", "BANK", "MOBILE MONEY"]),
                payer_name=fake.name(),
                _metadata={}
            )
            for _ in range(CONFIG.NUM_EMPLOYEES)
        ]
        return self.get_or_create_objects('employee', 'Employee', instances, 'employees')

    def get_or_create_leave_type(self):
        model = self._get_model('leave', 'TypeOfLeave')
        leaves = [
            ("Congé annuel", "repos annuel", 5, 30, 365),
            ("Congé maladie", "problèmes de santé", 1, 15, 0),
            ("Congé maternité", "naissance", 14, 98, 0),
        ]
        instances = [
            model(
                name=name,
                description=desc,
                min_duration=mini,
                max_duration=maxi,
                eligibility_after_days=days,
                _metadata={},
                sub_organization=self.suborganization
            )
            for name, desc, mini, maxi, days in leaves
        ]
        return self.get_or_create_objects('leave', 'TypeOfLeave', instances, 'leave types')

    def get_or_create_legal_payslip_element(self):
        model = self._get_model('payroll', 'LegalItem')
        items = [
            ("INPP", -1, "Inpp", "0", "0", "1"),
            ("IPR", -1, "Impôt sur revenu", "0", "ipr_iere", "1"),
            ("ONEM", -1, "Onem", "sum_of('taxable_amount') * 0.02", "0", "1"),
            ("CNSS", -1, "Sécurité Sociale", "sum_of('social_security_amount') * 0.13", "sum_of('social_security_amount') * 0.05", "1"),
        ]
        instances = [
            model(
                code=code,
                type_of_item=typ,
                name=name,
                formula_qp_employer=emp,
                formula_qp_employee=empl,
                condition=cond,
                is_actif=True,
                sub_organization=self.suborganization
            )
            for code, typ, name, emp, empl, cond in items
        ]
        return self.get_or_create_objects('payroll', 'LegalItem', instances, 'legal items')

    def get_or_create_payslip_element(self, grades):
        model = self._get_model('payroll', 'Item')
        unique_keys = set()
        for grade in grades:
            unique_keys.update(grade._metadata.keys())

        instances = [
            model(
                code=key.upper(),
                type_of_item=1,
                name=key.replace("_", " ").capitalize(),
                formula_qp_employee=f"employee.grade.{key}",
                formula_qp_employer="0",
                condition="employee.status != None",
                time="employee.attendance",
                is_social_security=key in ["base", "prime_ind"],
                is_taxable=key in ["base", "prime_ind"],
                is_bonus="prime_ind" in key,
                is_payable=True,
                sub_organization=self.suborganization
            )
            for key in unique_keys
        ]
        return self.get_or_create_objects('payroll', 'Item', instances, 'payslip elements')
