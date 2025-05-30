import logging
import requests
from celery import shared_task
from django.conf import settings

from payroll.models import PaidEmployee

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
    api_url = getattr(settings, "ONAFRIQ_API_URL", "https://api.onafriq.com/api/v5/payments")

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
        try:
            logger.info(f"Sending payment request for {employee['full_name']} ({employee['mobile_number']})")
            
            response = requests.post(api_url, json=employee, headers=headers, timeout=15)
            response.raise_for_status()  # Raise an error for bad HTTP responses
            
            result = response.json()
            logger.info(f"Payment successful for {employee['full_name']}: {result}")

        except requests.Timeout:
            logger.warning(f"Timeout error for {employee['full_name']}. Adding to retry list.")
            failed_payments.append(employee)  # Collect failed requests for retry later

        except requests.RequestException as e:
            logger.error(f"Payment request failed for {employee['full_name']}: {str(e)}", exc_info=True)
            failed_payments.append(employee)  # Collect failed requests for further inspection
            
        except Exception as e:
            logger.error(f"Payment request failed for {employee['full_name']}: {str(e)}", exc_info=True)
            failed_payments.append(employee)  # Collect failed requests for further inspection

    # Update the model updated
    qs = PaidEmployee.objects.filter(payroll_id=payroll_id)

    qs_scheduled = qs.filter(
        id__in = [payment.get("metadata", {}).get("payroll_paidemployee_id", None) for payment in scheduled_payments]
    ).update(
        _metadata={**F('_metadata'), 'easypay_mobile_payment_status': 'scheduled'}
    )

    qs_failed = qs.filter(
        id__in = [payment.get("metadata", {}).get("payroll_paidemployee_id", None) for payment in failed_payments]
    ).updated(
        _metadata={**F('_metadata'), 'easypay_mobile_payment_status': 'failed'}
    )

    # Return results with failed payments
    return {
        "status": "success",
        "processed_count": len(employees) - len(failed_payments),
        "failed_count": len(failed_payments),
        "failed_payments": failed_payments
    }