import requests
from django.conf import settings
from tenacity import retry, stop_after_attempt, wait_none, retry_if_exception_type, before_sleep_log
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class LagoClient:
    """
    Handles interactions with the Lago API for customer, plan, and subscription management.
    """

    def __init__(self):
        self.api_url: str = getattr(settings, 'LAGO_API_URL', 'http://lago:3000')
        self.api_key: str = getattr(settings, 'LAGO_API_KEY', '23e0a6aa-a0a7-4dc9-bec6-e225bf65ec05')
        if not self.api_key:
            raise ValueError('LAGO_API_KEY is not configured')
        self.headers = {'Authorization': f'Bearer {self.api_key}'}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_none(),
        retry=retry_if_exception_type((requests.RequestException,)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def is_customer_unique(self, external_id: str) -> bool:
        """
        Check if a customer with the given external_id exists in Lago.
        """
        url = f'{self.api_url}/api/v1/customers/{external_id}'
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            return False
        elif response.status_code != 404:
            raise ValueError(f'Failed to check Lago customer existence: {response.text}')
        return True

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_none(),
        retry=retry_if_exception_type((requests.RequestException,)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def is_valid_plan(self, plan_code: str) -> bool:
        """
        Check if the plan code is valid and active in Lago.
        """
        url = f'{self.api_url}/api/v1/plans'
        response = requests.get(url, headers=self.headers)
        if response.status_code != 200:
            raise ValueError(f'Failed to fetch plans from Lago: {response.text}')
        plans = response.json().get('plans', [])
        return any(p['code'] == plan_code and not p.get('archived', False) for p in plans)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_none(),
        retry=retry_if_exception_type((requests.RequestException, ValueError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def create_customer(self, external_id: str, email: str, name: Optional[str]) -> Dict[str, Any]:
        """
        Create a customer in Lago with the schema as external_id.
        """
        url = f'{self.api_url}/api/v1/customers'
        payload = {
            'customer': {
                'email': email,
                'external_id': external_id,
                'name': name or external_id.title(),
                'currency': getattr(settings, 'DEFAULT_CURRENCY', 'CDF'),
                'timezone': getattr(settings, 'TIME_ZONE', 'Africa/Kinshasa')
            }
        }
        response = requests.post(url, json=payload, headers=self.headers)
        if response.status_code != 200:
            raise ValueError(f'Failed to create Lago customer: {response.text}')
        return response.json().get('customer')

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_none(),
        retry=retry_if_exception_type((requests.RequestException, ValueError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def assign_plan(self, external_id: str, plan_code: str) -> Dict[str, Any]:
        """
        Assign an active plan to the customer via a Lago subscription.
        """
        url = f'{self.api_url}/api/v1/subscriptions'
        payload = {
            'subscription': {
                'external_customer_id': external_id,
                'external_id': external_id,
                'plan_code': plan_code
            }
        }
        response = requests.post(url, json=payload, headers=self.headers)
        if response.status_code != 200:
            raise ValueError(f'Failed to create Lago subscription: {response.text}')
        return response.json().get('subscription')

    def cleanup(self, external_id: str) -> None:
        """
        Clean up Lago customer and subscription on failure.
        """
        try:
            self.terminate_subscription(external_id)
            self.delete_customer(external_id)
        except Exception as e:
            logger.warning(f'Failed to clean up Lago for external_id "{external_id}": {str(e)}')

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_none(),
        retry=retry_if_exception_type((requests.RequestException,)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def terminate_subscription(self, external_id: str) -> None:
        """
        Terminate any active subscriptions for the customer.
        """
        url = f'{self.api_url}/api/v1/subscriptions'
        params = {'external_customer_id': external_id, 'status[]': 'active'}
        response = requests.get(url, params=params, headers=self.headers)
        if response.status_code != 200:
            logger.warning(f'Failed to fetch subscriptions for cleanup: {response.text}')
            return
        subscriptions = response.json().get('subscriptions', [])
        for sub in subscriptions:
            sub_id = sub.get('lago_id')
            if sub_id:
                delete_url = f'{self.api_url}/api/v1/subscriptions/{sub_id}'
                delete_response = requests.delete(delete_url, headers=self.headers)
                if delete_response.status_code == 200:
                    logger.info(f'Terminated subscription "{sub_id}" for external_id "{external_id}"')
                else:
                    logger.warning(f'Failed to terminate subscription "{sub_id}": {delete_response.text}')

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_none(),
        retry=retry_if_exception_type((requests.RequestException,)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def delete_customer(self, external_id: str) -> None:
        """
        Delete a Lago customer.
        """
        url = f'{self.api_url}/api/v1/customers/{external_id}'
        response = requests.delete(url, headers=self.headers)
        if response.status_code != 200:
            logger.warning(f'Failed to delete Lago customer "{external_id}": {response.text}')
        else:
            logger.info(f'Deleted Lago customer "{external_id}"')