import logging
import requests
from celery import shared_task
from django.conf import settings

from payroll.models import PaidEmployee
from django.db.models import F

# Configure logging
logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_mobile_payment(self, payroll_id, employees):
    """
    Celery task to process mobile payments for multiple employees via Onafriq API.
    Handles retries in case of network failures.
    """

    if not employees:
        logger.warning("No employees provided for payment processing.")
        return {"status": "error", "error": "Empty employee list"}

    # Retrieve Onafriq token and API URL
    ONAFRIQ_TOKEN = getattr(settings, "ONAFRIQ_TOKEN", None)
    api_url = getattr(settings, "ONAFRIQ_API_URL",
                      "https://api.onafriq.com/api/v5/payments")

    if not ONAFRIQ_TOKEN:
        logger.error("Onafriq token missing. Cannot proceed with payments.")
        return {"status": "error", "error": "Onafriq token missing"}

    headers = {
        "Authorization": f"Token {ONAFRIQ_TOKEN}",
        "Content-Type": "application/json"
    }

    # Lists to track failed transactions
    scheduled_payments = []
    failed_payments = []

    for employee in employees:
        # exemple = {'description': 'Payroll Paie mois de mai 2 for Kabeya Ilunga', 'phonenumber': PhoneNumber(country_code=243, national_number=891234567, extension=None, italian_leading_zero=None, number_of_leading_zeros=None, country_code_source=1, preferred_domestic_carrier_code=None), 'first_name': 'Jean',
        #            'last_name': 'Kabeya', 'account': '2956481', 'currency': 'CDF', 'amount': 1.0, 'request_currency': 'CDF', 'payment_type': 'money', 'metadata': {'easypay_mobile_id': 18, 'payroll_paidemployee_id': 14, 'payroll_payroll_id': 6, 'employee_employee_id': 'BIO123456894833398337474'}}
        employee['full_name'] = f"{employee['first_name']} {employee['last_name']}"
        employee['phonenumber'] = str(employee['phonenumber'])
        employee['metadata'] = {
            "easypay_mobile_id": employee['metadata'].get('easypay_mobile_id', None),
            "paidemployee_id": employee['metadata'].get('payroll_paidemployee_id', None),
            "payroll_id": employee['metadata'].get('payroll_payroll_id', None),
            "employee_id": employee['metadata'].get('employee_employee_id', None)
        }
        try:
            logger.info(
                f"Sending payment request for {employee['full_name']} ({str(employee['phonenumber'])})")
            response = requests.post(
                api_url, json=employee, headers=headers, timeout=15)
            # response.raise_for_status()  # Raise an error for bad HTTP responses
            print(response.json())
            # print(employee)

            result = response.json()
            logger.info(
                f"Payment successful for {employee['full_name']}: {result}")

        except requests.Timeout:
            logger.warning(
                f"Timeout error for {employee['full_name']}. Adding to retry list.")
            # Collect failed requests for retry later
            failed_payments.append(employee)

        except requests.RequestException as e:
            logger.error(
                f"Payment request failed for {employee['full_name']}: {str(e)}", exc_info=True)
            # Collect failed requests for further inspection
            failed_payments.append(employee)

        except Exception as e:
            logger.error(
                f"Payment request failed for {employee['full_name']}: {str(e)}", exc_info=True)
            # Collect failed requests for further inspection
            failed_payments.append(employee)

    # Update the model updated
    qs = PaidEmployee.objects.filter(payroll_id=payroll_id)

    # qs_scheduled = qs.filter(
    #     id__in=[payment.get("metadata", {}).get(
    #         "payroll_paidemployee_id", None) for payment in scheduled_payments]
    # ).update(
    #     _metadata={**F('_metadata'),
    #                'easypay_mobile_payment_status': 'scheduled'}
    # )

    scheduled_ids = [
        payment.get("metadata", {}).get("paidemployee_id")
        for payment in scheduled_payments
        if payment.get("metadata", {}).get("paidemployee_id") is not None
    ]

    for obj in PaidEmployee.objects.filter(id__in=scheduled_ids):
        metadata = obj._metadata or {}
        metadata["easypay_mobile_payment_status"] = "scheduled"
        obj._metadata = metadata
        obj.save(update_fields=["_metadata"])

    # qs_failed = qs.filter(
    #     id__in=[payment.get("metadata", {}).get(
    #         "payroll_paidemployee_id", None) for payment in failed_payments]
    # ).updated(
    #     _metadata={**F('_metadata'), 'easypay_mobile_payment_status': 'failed'}
    # )

    failed_ids = [
        payment.get("metadata", {}).get("paidemployee_id")
        for payment in failed_payments
        if payment.get("metadata", {}).get("paidemployee_id") is not None
    ]

    for obj in PaidEmployee.objects.filter(id__in=failed_ids):
        metadata = obj._metadata or {}
        metadata = {**metadata, "easypay_mobile_payment_status": "failed"}
        obj._metadata = metadata
        obj.save(update_fields=["_metadata"])

    # Return results with failed payments
    return {
        "status": "success",
        "processed_count": len(employees) - len(failed_payments),
        "failed_count": len(failed_payments),
        "failed_payments": failed_payments
    }
