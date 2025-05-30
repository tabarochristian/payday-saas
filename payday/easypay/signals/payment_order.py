import logging
import requests
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import F, Value
from django.db.models.functions import Concat
from django.db import models
from easypay.models import Mobile
from payroll.models import PaidEmployee
from payday import settings
from easypay.tasks import send_mobile_payment  # Celery task

# Configure logging
logger = logging.getLogger(__name__)

@receiver(post_save, sender=Mobile)
def mobile_payment_order_created(sender, instance, created, **kwargs):
    """Triggers mobile money payments when a Mobile instance is created."""
    if not created:
        return

    try:
        # Fetch employees eligible for mobile money payment
        employees = PaidEmployee.objects.filter(
            payment_method='MOBILE MONEY',
            payroll=instance.payroll
        ).exclude(
            mobile_number__isnull=True
        ).exclude(
            mobile_number=''
        ).annotate(
            full_name=Concat(F('last_name'), Value(' '), F('middle_name'), output_field=models.CharField())
        ).values(
            'mobile_number', 'employee_id', 'payroll_id', 'first_name', 
            'last_name', 'full_name', 'net', 'id'
        )

        # Retrieve settings with default fallback
        onafriq_account = getattr(settings, "ONAFRIQ_SYCAMORE_ACC_NO", "2956481")
        currency = getattr(settings, "DEFAULT_PAYROLL_CURRENCY", "CDF")

        # Prepare payment data
        payments = [
            {
                "description": f"Payroll {instance.payroll.name} for {employee['full_name']}",
                "phonenumber": employee["mobile_number"],
                "first_name": employee["first_name"],
                "last_name": employee["last_name"],
                "account": onafriq_account,
                "currency": currency,
                "amount": float(employee['net']),
                "request_currency": currency,
                "payment_type": "money",
                "metadata": {
                    "easypay_mobile_id": instance.id,
                    "payroll_paidemployee_id": employee["id"],
                    "payroll_payroll_id": employee["payroll_id"],
                    "employee_employee_id": employee["employee_id"]
                }
            }
            for employee in employees
        ]

        if not payments:
            instance.status = "COMPLETED"
            return instance.save(update_fields=["status"])
            
        debug_mode = getattr(settings, "DEBUG", True)
        send_payment = send_mobile_payment if debug_mode else send_mobile_payment.delay
        send_payment(instance.payroll.id, payments)
        
        instance.status = "PROCESSING"
        instance.save(update_fields=["status"])
        logger.info(f"Processed {len(payments)} mobile payments for payroll {instance.payroll.name}.")

    except Exception as e:
        logger.error(f"Error processing mobile payments: {str(e)}", exc_info=True)
