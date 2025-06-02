import random
import logging
from faker import Faker
from django.apps import apps
from django.core.management.base import BaseCommand
from django.db.utils import IntegrityError
from django.conf import settings
from typing import List, Any, Tuple, Dict
from dataclasses import dataclass
from functools import lru_cache
from django.conf import settings
from core.utils import DictToObject, set_schema

# Configuration
@dataclass
class Config:
    LOG_FILE: str = "seed.log"
    LOG_LEVEL: str = getattr(settings, 'LOGGING', {}).get('level', 'INFO')
    NUM_EMPLOYEES: int = 50
    BATCH_SIZE: int = 100
    FAKER_LOCALE: str = "fr_FR"

CONFIG = Config()

# Configure logging
logging.basicConfig(
    filename=CONFIG.LOG_FILE,
    level=CONFIG.LOG_LEVEL,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

fake = Faker(CONFIG.FAKER_LOCALE)

class Command(BaseCommand):
    help = "Generate fake data dynamically for models in a specified app"

    def add_arguments(self, parser):
        parser.add_argument('schema', type=str, help='The schema name (subdomain) for the tenant')

    def handle(self, *args, **kwargs) -> None:
        """Main method to orchestrate data seeding"""

        schema: str = kwargs['schema'].lower()

        debug = getattr(settings, 'DEBUG', True)
        if not debug:
            set_schema(schema)

        try:
            logger.info("Starting data seeding process", extra={'app': 'employee'})
            
            grades = self.get_or_create_fake_grade()
            logger.info(f"Processed {len(grades)} grades", extra={'model': 'Grade'})

            statuses = self.get_or_create_status()
            logger.info(f"Processed {len(statuses)} statuses", extra={'model': 'Status'})

            branches = self.get_or_create_branch()
            logger.info(f"Processed {len(branches)} branches", extra={'model': 'Branch'})

            agreements = self.get_or_create_agreement()
            logger.info(f"Processed {len(agreements)} agreements", extra={'model': 'Agreement'})

            directions = self.get_or_create_direction()
            logger.info(f"Processed {len(directions)} directions", extra={'model': 'Direction'})

            designations = self.get_or_create_designation()
            logger.info(f"Processed {len(designations)} designations", extra={'model': 'Designation'})

            employees = self.get_or_create_employee(
                grades, statuses, branches, agreements, directions, designations, 
                num_samples=CONFIG.NUM_EMPLOYEES
            )
            logger.info(f"Processed {len(employees)} employees", extra={'model': 'Employee'})

            leaves = self.get_or_create_leave_type()
            logger.info(f"Processed {len(leaves)} leave types", extra={'model': 'TypeOfLeave'})

            legal_payslips = self.get_or_create_legal_payslip_element()
            logger.info(f"Processed {len(legal_payslips)} legal payslip elements", 
                       extra={'model': 'LegalItem'})

            payslip_elements = self.get_or_create_payslip_element(grades)
            logger.info(f"Processed {len(payslip_elements)} payslip elements", 
                       extra={'model': 'Item'})

            logger.info("Data seeding completed successfully", extra={'app': 'employee'})
            
        except Exception as e:
            logger.error(f"Data seeding failed: {str(e)}", exc_info=True)
            raise

    @lru_cache(maxsize=32)
    def _get_model(self, app_label: str, model_name: str) -> Any:
        """Cached model retrieval"""
        try:
            return apps.get_model(app_label, model_name)
        except LookupError:
            logger.error(f"Model '{model_name}' not found in app '{app_label}'", 
                        extra={'app_label': app_label, 'model_name': model_name})
            raise

    def get_or_create_payslip_element(self, grades: List[Any]) -> List[Any]:
        """Create or retrieve payslip elements"""
        model = self._get_model('payroll', 'Item')
        qs = model.objects.all()
        if qs.exists():
            logger.info("Returning existing payslip elements", extra={'model': 'Item'})
            return list(qs)

        unique_keys = set()
        for grade in grades:
            unique_keys.update(grade._metadata.keys())

        payslip_elements = [
            model(
                code=f"{key.upper()}",
                type_of_item=1,
                name=f"{key.replace('_', ' ').capitalize()}",
                formula_qp_employer="0",
                formula_qp_employee=f"employee.grade.{key}",
                condition="employee.status != None and employee.status.group == 'ACTIF'",
                time="employee.attendance",
                is_social_security=(key in ["base", "prime_ind"]),
                is_taxable=(key in ["base", "prime_ind"]),
                is_bonus=("prime_ind" in key),
                is_payable=True
            )
            for key in unique_keys
        ]

        try:
            model.objects.bulk_create(payslip_elements, batch_size=CONFIG.BATCH_SIZE)
            logger.info(f"Created {len(payslip_elements)} new payslip elements", 
                       extra={'model': 'Item'})
        except IntegrityError as e:
            logger.error(f"Failed to create payslip elements: {str(e)}", 
                        exc_info=True, extra={'model': 'Item'})
            raise

        return list(model.objects.all())

    def get_or_create_legal_payslip_element(self) -> List[Any]:
        """Create or retrieve legal payslip elements"""
        model = self._get_model('payroll', 'LegalItem')
        qs = model.objects.all()
        if qs.exists():
            logger.info("Returning existing legal payslip elements", extra={'model': 'LegalItem'})
            return list(qs)

        legal_elements_list = [
            (
                "IPR", -1, "Impôt Professionnel sur le Revenu",
                "0", "ipr_iere(df_items, employee)", 
                "employee.status.group == 'ACTIF'"
            ),
            (
                "CNSS", -1, "Caisse Nationale de Sécurité Sociale",
                "sum_of_items_fields(df_items, 'social_security_amount') * 0.13", 
                "sum_of_items_fields(df_items, 'social_security_amount') * 0.05", 
                "employee.status.group == 'ACTIF'"
            ),
            (
                "INPP", -1, "Institut National de Préparation Professionnelle",
                "sum_of_items_fields(df_items, 'taxable_amount') * 0.03", "0", 
                "employee.status.group == 'ACTIF'"
            ),
            (
                "ONEM", -1, "Office National de l’Emploi",
                "sum_of_items_fields(df_items, 'taxable_amount') * 0.002", "0", 
                "employee.status.group == 'ACTIF'"
            )
        ]

        legal_instances = [
            model(
                code=code,
                type_of_item=type_of_item,
                name=name,
                formula_qp_employer=formula_qp_employer,
                formula_qp_employee=formula_qp_employee,
                condition=condition,
                is_actif=True
            )
            for code, type_of_item, name, formula_qp_employer, formula_qp_employee, condition in legal_elements_list
        ]

        try:
            model.objects.bulk_create(legal_instances, batch_size=CONFIG.BATCH_SIZE)
            logger.info(f"Created {len(legal_instances)} new legal payslip elements", 
                       extra={'model': 'LegalItem'})
        except IntegrityError as e:
            logger.error(f"Failed to create legal payslip elements: {str(e)}", 
                        exc_info=True, extra={'model': 'LegalItem'})
            raise

        return list(model.objects.all())

    def get_or_create_leave_type(self) -> List[Any]:
        """Create or retrieve leave types"""
        model = self._get_model('leave', 'TypeOfLeave')
        qs = model.objects.all()
        if qs.exists():
            logger.info("Returning existing leave types", extra={'model': 'TypeOfLeave'})
            return list(qs)

        leave_type_list = [
            (
                "Congé annuel",
                "Congé payé accordé chaque année pour repos.",
                5, 30, 365,
                {"payé": True, "justificatif": "Non requis", "prolongeable": True}
            ),
            (
                "Congé de maladie",
                "Congé accordé en cas de problème de santé.",
                1, 15, 0,
                {"payé": True, "justificatif": "Certificat médical requis", "prolongeable": False}
            ),
            (
                "Congé maternité",
                "Congé réservé aux employées enceintes avant et après l’accouchement.",
                14, 98, 0,
                {"payé": True, "justificatif": "Acte médical requis", "prolongeable": False}
            ),
            (
                "Congé paternité",
                "Congé accordé aux nouveaux pères à la naissance d’un enfant.",
                3, 10, 0,
                {"payé": True, "justificatif": "Extrait de naissance requis", "prolongeable": False}
            ),
            (
                "Congé sans solde",
                "Congé accordé sous autorisation spéciale, sans rémunération.",
                5, 90, 180,
                {"payé": False, "justificatif": "Motif personnel ou professionnel", "prolongeable": True}
            ),
            (
                "Congé de mission",
                "Congé temporaire pour affectation professionnelle à l’étranger ou sur un site.",
                1, 60, 0,
                {"payé": True, "justificatif": "Ordre de mission requis", "prolongeable": True}
            ),
        ]

        leave_instances = [
            model(
                name=name,
                description=description,
                min_duration=min_duration,
                max_duration=max_duration,
                eligibility_after_days=eligibility_after_days,
                _metadata=metadata
            )
            for name, description, min_duration, max_duration, eligibility_after_days, metadata in leave_type_list
        ]

        try:
            model.objects.bulk_create(leave_instances, batch_size=CONFIG.BATCH_SIZE)
            logger.info(f"Created {len(leave_instances)} new leave types", 
                       extra={'model': 'TypeOfLeave'})
        except IntegrityError as e:
            logger.error(f"Failed to create leave types: {str(e)}", 
                        exc_info=True, extra={'model': 'TypeOfLeave'})
            raise

        return list(model.objects.all())

    def get_or_create_employee(self, grades: List[Any], statuses: List[Any], 
                            branches: List[Any], agreements: List[Any], 
                            directions: List[Any], designations: List[Any], 
                            num_samples: int) -> List[Any]:
        """Create or retrieve employees"""
        model = self._get_model('employee', 'Employee')
        qs = model.objects.all()
        if qs.exists():
            logger.info("Returning existing employees", extra={'model': 'Employee'})
            return list(qs)

        employees_instances = [
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
                payment_account=fake.iban(),
                payment_method=random.choice(["CASH", "BANK", "MOBILE MONEY"]),
                payer_name=fake.name(),
                _metadata={}
            )
            for _ in range(num_samples)
        ]

        try:
            model.objects.bulk_create(employees_instances, batch_size=CONFIG.BATCH_SIZE)
            logger.info(f"Created {len(employees_instances)} new employees", 
                       extra={'model': 'Employee'})
        except IntegrityError as e:
            logger.error(f"Failed to create employees: {str(e)}", 
                        exc_info=True, extra={'model': 'Employee'})
            raise

        return list(model.objects.all())

    def get_or_create_designation(self) -> List[Any]:
        """Create or retrieve designations"""
        model = self._get_model('employee', 'Designation')
        qs = model.objects.all()
        if qs.exists():
            logger.info("Returning existing designations", extra={'model': 'Designation'})
            return list(qs)

        designation_list = [
            ("Directeur Général", {"catégorie": "Direction", "niveau": "Exécutif", "responsabilité": "Stratégique"}),
            ("Responsable RH", {"catégorie": "Ressources Humaines", "niveau": "Cadre", "responsabilité": "Gestion des employés"}),
            ("Responsable Financier", {"catégorie": "Finance", "niveau": "Cadre supérieur", "responsabilité": "Suivi des finances"}),
            ("Ingénieur Informatique", {"catégorie": "IT & Digital", "niveau": "Intermédiaire", "responsabilité": "Développement technologique"}),
            ("Commercial Senior", {"catégorie": "Ventes", "niveau": "Expérimenté", "responsabilité": "Stratégie commerciale"}),
        ]

        designation_instances = [
            model(name=name, _metadata=metadata)
            for name, metadata in designation_list
        ]

        try:
            model.objects.bulk_create(designation_instances, batch_size=CONFIG.BATCH_SIZE)
            logger.info(f"Created {len(designation_instances)} new designations", 
                       extra={'model': 'Designation'})
        except IntegrityError as e:
            logger.error(f"Failed to create designations: {str(e)}", 
                        exc_info=True, extra={'model': 'Designation'})
            raise

        return list(model.objects.all())

    def get_or_create_direction(self) -> List[Any]:
        """Create or retrieve directions"""
        model = self._get_model('employee', 'Direction')
        qs = model.objects.all()
        if qs.exists():
            logger.info("Returning existing directions", extra={'model': 'Direction'})
            return list(qs)

        direction_list = [
            ("Direction Générale", {"responsable": "PDG", "budget_annuel": "10M CDF", "est_strategique": True}),
            ("Ressources Humaines", {"responsable": "Directeur RH", "budget_annuel": "2M CDF", "est_strategique": True}),
            ("Finance", {"responsable": "Directeur Financier", "budget_annuel": "5M CDF", "est_strategique": True}),
            ("Informatique & Digital", {"responsable": "CTO", "budget_annuel": "3M CDF", "est_strategique": False}),
            ("Commercial", {"responsable": "Directeur Commercial", "budget_annuel": "4M CDF", "est_strategique": True}),
        ]

        direction_instances = [
            model(name=name, _metadata=metadata)
            for name, metadata in direction_list
        ]

        try:
            model.objects.bulk_create(direction_instances, batch_size=CONFIG.BATCH_SIZE)
            logger.info(f"Created {len(direction_instances)} new directions", 
                       extra={'model': 'Direction'})
        except IntegrityError as e:
            logger.error(f"Failed to create directions: {str(e)}", 
                        exc_info=True, extra={'model': 'Direction'})
            raise

        return list(model.objects.all())

    def get_or_create_agreement(self) -> List[Any]:
        """Create or retrieve agreements"""
        model = self._get_model('employee', 'Agreement')
        qs = model.objects.all()
        if qs.exists():
            logger.info("Returning existing agreements", extra={'model': 'Agreement'})
            return list(qs)

        agreement_list = [
            ("CDI", {"durée": "indéterminée", "renouvelable": False, "période_essai": "3 mois", "avantages": True}),
            ("CDD", {"durée": "12 mois", "renouvelable": True, "période_essai": "1 mois", "avantages": True}),
            ("Stage", {"durée": "6 mois", "renouvelable": False, "période_essai": "N/A", "avantages": False}),
            ("Freelance", {"durée": "basé sur le projet", "renouvelable": True, "période_essai": "N/A", "avantages": False}),
            ("Consultant", {"durée": "basé sur le contrat", "renouvelable": True, "période_essai": "N/A", "avantages": True}),
        ]

        agreement_instances = [
            model(name=name, _metadata=metadata)
            for name, metadata in agreement_list
        ]

        try:
            model.objects.bulk_create(agreement_instances, batch_size=CONFIG.BATCH_SIZE)
            logger.info(f"Created {len(agreement_instances)} new agreements", 
                       extra={'model': 'Agreement'})
        except IntegrityError as e:
            logger.error(f"Failed to create agreements: {str(e)}", 
                        exc_info=True, extra={'model': 'Agreement'})
            raise

        return list(model.objects.all())

    def get_or_create_branch(self) -> List[Any]:
        """Create or retrieve branches"""
        model = self._get_model('employee', 'Branch')
        qs = model.objects.all()
        if qs.exists():
            logger.info("Returning existing branches", extra={'model': 'Branch'})
            return list(qs)

        branch_list = [
            ("Kinshasa", 5_000),
            ("Lubumbashi", 4_500),
            ("Goma", 6_000),
            ("Kisangani", 4_000),
            ("Matadi", 3_500),
        ]

        branch_instances = [
            model(name=name, _metadata={"taxi_price": price})
            for name, price in branch_list
        ]

        try:
            model.objects.bulk_create(branch_instances, batch_size=CONFIG.BATCH_SIZE)
            logger.info(f"Created {len(branch_instances)} new branches", 
                       extra={'model': 'Branch'})
        except IntegrityError as e:
            logger.error(f"Failed to create branches: {str(e)}", 
                        exc_info=True, extra={'model': 'Branch'})
            raise

        return list(model.objects.all())

    def get_or_create_status(self) -> List[Any]:
        """Create or retrieve statuses"""
        model = self._get_model('employee', 'Status')
        qs = model.objects.all()
        if qs.exists():
            logger.info("Returning existing statuses", extra={'model': 'Status'})
            return list(qs)

        status_list = [
            ("ACTIF", "en service", True),
            ("ACTIF", "en congé", True),
            ("INACTIF", "en suspension", False),
            ("ACTIF", "en mission", True),
            ("INACTIF", "retiré", False),
        ]

        status_instances = [
            model(name=name, group=group, _metadata={"est_actif": is_active})
            for group, name, is_active in status_list
        ]

        try:
            model.objects.bulk_create(status_instances, batch_size=CONFIG.BATCH_SIZE)
            logger.info(f"Created {len(status_instances)} new statuses", 
                       extra={'model': 'Status'})
        except IntegrityError as e:
            logger.error(f"Failed to create statuses: {str(e)}", 
                        exc_info=True, extra={'model': 'Status'})
            raise

        return list(model.objects.all())

    def get_or_create_fake_grade(self) -> List[Any]:
        """Create or retrieve grades"""
        model = self._get_model('employee', 'Grade')
        qs = model.objects.all()
        if qs.exists():
            logger.info("Returning existing grades", extra={'model': 'Grade'})
            return list(qs)

        grades_list = ["directeur", "manager", "collaborateur", "subalterne"]
        compute_value = lambda base, index: base * ((4 - index) / 10) if index > 0 else base

        grades_instances = [
            model(
                name=name,
                group=name.upper(),
                _metadata={
                    "base": compute_value(2_000_000, index),
                    "transport": compute_value(200_000, index),
                    "logement": compute_value(400_000, index),
                    "prime_ind": compute_value(250_000, index),
                    "all_fam": compute_value(150_000, index),
                }
            )
            for index, name in enumerate(grades_list)
        ]

        try:
            model.objects.bulk_create(grades_instances, batch_size=CONFIG.BATCH_SIZE)
            logger.info(f"Created {len(grades_instances)} new grades", 
                       extra={'model': 'Grade'})
        except IntegrityError as e:
            logger.error(f"Failed to create grades: {str(e)}", 
                        exc_info=True, extra={'model': 'Grade'})
            raise

        return list(model.objects.all())