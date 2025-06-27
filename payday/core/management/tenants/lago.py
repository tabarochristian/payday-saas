import requests
from django.conf import settings
from tenacity import retry, stop_after_attempt, wait_none, retry_if_exception_type, before_sleep_log
import logging
from typing import Optional, Dict, Any
from dateutil import parser
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class LagoClient:
    """
    Handles interactions with the Lago API for customer, plan, subscription, and coupon management.
    """

    def __init__(self):
        self.api_url: str = getattr(settings, 'LAGO_API_URL', 'http://lago:3000')
        self.api_key: str = getattr(settings, 'LAGO_API_KEY', '23e0a6aa-a0a7-4dc9-bec6-e225bf65ec05')
        self.api_url += "/api/v1"
        if not self.api_key:
            raise ValueError('LAGO_API_KEY is not configured')
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_none(),
        retry=retry_if_exception_type((requests.RequestException,)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def is_customer_unique(self, external_id: str) -> bool:
        url = f'{self.api_url}/customers/{external_id}'
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
        url = f'{self.api_url}/plans'
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
        url = f'{self.api_url}/customers'
        payload = {
            'customer': {
                'email': email,
                'external_id': external_id,
                'name': name or external_id.title(),
                'currency': getattr(settings, 'DEFAULT_CURRENCY', 'USD'),
                'timezone': getattr(settings, 'TIME_ZONE', 'Africa/Kinshasa'),
                'customer_type': 'company',
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
        url = f'{self.api_url}/subscriptions'
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
        url = f'{self.api_url}/subscriptions'
        params = {'external_customer_id': external_id, 'status[]': 'active'}
        response = requests.get(url, params=params, headers=self.headers)
        if response.status_code != 200:
            logger.warning(f'Failed to fetch subscriptions for cleanup: {response.text}')
            return
        subscriptions = response.json().get('subscriptions', [])
        for sub in subscriptions:
            sub_id = sub.get('lago_id')
            if sub_id:
                delete_url = f'{self.api_url}/subscriptions/{sub_id}'
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
        url = f'{self.api_url}/customers/{external_id}'
        response = requests.delete(url, headers=self.headers)
        if response.status_code != 200:
            logger.warning(f'Failed to delete Lago customer "{external_id}": {response.text}')
        else:
            logger.info(f'Deleted Lago customer "{external_id}"')

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_none(),
        retry=retry_if_exception_type((requests.RequestException,)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def is_valid_coupon(self, coupon_code: str) -> bool:
        url = f'{self.api_url}/coupons/{coupon_code}'
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            coupon = response.json().get('coupon', {})
            if coupon.get('archived', False):
                return False
            expiration = coupon.get('expiration_at')
            if expiration:
                expiration_dt = parser.isoparse(expiration)
                if expiration_dt < datetime.now(timezone.utc):
                    return False
            return True
        elif response.status_code == 404:
            return False
        else:
            raise ValueError(f'Failed to fetch coupon "{coupon_code}": {response.status_code} {response.text}')

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_none(),
        retry=retry_if_exception_type((requests.RequestException, ValueError)),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def assign_coupon(self, external_id: str, email: str, name: Optional[str], coupon_code: str) -> Dict[str, Any]:
        """
        Apply a coupon to an existing customer using Lago's POST /applied_coupons API.
        Does NOT create a customer. Raises an error if the customer does not exist.
        """

        # Ensure the customer exists
        if self.is_customer_unique(external_id):
            raise ValueError(f'Cannot assign coupon: customer "{external_id}" does not exist in Lago.')

        # Validate the coupon
        if not self.is_valid_coupon(coupon_code):
            raise ValueError(f'Coupon code "{coupon_code}" is invalid, expired, or archived.')

        # Assign the coupon
        url = f'{self.api_url}/applied_coupons'
        payload = {
            "applied_coupon": {
                "external_customer_id": external_id,
                "coupon_code": coupon_code
            }
        }

        response = requests.post(url, json=payload, headers=self.headers)

        if response.status_code == 200:
            data = response.json().get('applied_coupon')
            if not data:
                raise ValueError(f'Successful response but missing "applied_coupon" data: {response.text}')
            logger.info(f'Coupon "{coupon_code}" successfully applied to customer "{external_id}"')
            return data

        elif response.status_code == 422:
            detail = response.json().get('error', {}).get('message', '')
            raise ValueError(f'Failed to assign coupon "{coupon_code}" to "{external_id}": {detail or response.text}')

        else:
            raise ValueError(f'Unexpected error applying coupon "{coupon_code}": {response.status_code} {response.text}')


