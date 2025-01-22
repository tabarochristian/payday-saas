import requests
import logging
import os

import base64
import json

from django.utils.translation import gettext as _
from django.shortcuts import get_object_or_404
from django.conf import settings

from employee.models import Employee
from core.models import Notification
from core.utils import set_schema
from celery import shared_task

logger = logging.getLogger(__name__)


def get_thumbor_image_base64(image_url, host="46.101.92.215", port=8888, width=480, height=640):
    """
    Generate a Thumbor URL, fetch the processed image, and return it as a base64-encoded string.

    Args:
        image_url (str): The URL of the source image.
        host (str): The Thumbor server host (default: "46.101.92.215").
        port (int): The Thumbor server port (default: 8888).
        width (int): The width of the output image (default: 480).
        height (int): The height of the output image (default: 640).

    Returns:
        str: The base64-encoded string of the processed image.
    """
    # Generate the Thumbor URL
    base_url = f"http://{host}:{port}/unsafe"
    filters = f"filters:face_detection():crop({width},{height})"
    thumbor_url = f"{base_url}/{width}x{height}/{filters}/{image_url}"

    # Fetch the processed image
    response = requests.get(thumbor_url)

    # Check if the request was successful
    if response.status_code == 200:
        # Encode the image content as base64
        return base64.b64encode(response.content).decode("utf-8")
    else:
        raise Exception(f"Failed to fetch the image. Status code: {response.status_code}")


class DeviceTask:
    """
    A helper class to handle image processing and device communication.
    """

    def process_employee_photo(self, employee):
        """
        Process the employee's photo to detect and crop the face using Thumbor.

        Args:
            employee (Employee): The employee object.

        Returns:
            str: The base64-encoded string of the processed image.

        Raises:
            ValueError: If the employee has no photo or Thumbor processing fails.
        """
        if not employee.photo:
            logger.error(f"Employee {employee.last_name} has no photo.")
            raise ValueError(_("Employee has no photo."))

        try:
            # Use Thumbor to process the image
            return get_thumbor_image_base64(employee.photo.url)
        except Exception as e:
            logger.error(f"Failed to process employee photo for {employee.last_name}: {e}")
            raise ValueError(_("Failed to process the employee's photo."))

    def send_to_device(self, device, employee, base64_image):
        """
        Send employee data and base64 image to the device.

        Args:
            device: The device object.
            employee (Employee): The employee object.
            base64_image (str): The base64-encoded image.

        Raises:
            Exception: If the request to the device fails.
        """
        print(json.dumps({
                    "sn": device.sn,
                    "cmd": "setuserinfo",
                    "enrollid": int(employee.registration_number),
                    "name": employee.last_name,
                    "backupnum": 50,
                    "record": base64_image,
                }))
        try:
            response = requests.post(
                "http://46.101.92.215:7788/send-command/",
                json={
                    "sn": device.sn,
                    "cmd": "setuserinfo",
                    "enrollid": int(employee.registration_number),
                    "name": employee.last_name,
                    "backupnum": 50,
                    "record": base64_image,
                }
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to send data to device {device.sn}. Error: {e}")
            raise


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': settings.CELERY_MAX_RETRIES, 'countdown': settings.CELERY_RETRY_DELAY},
)
def setuserinfo(self, tenant, pk):
    """
    Celery task to process an employee's photo and send it to associated devices.

    Args:
        tenant: The tenant schema.
        pk (int): The primary key of the employee.

    Returns:
        None
    """
    set_schema(tenant)

    employee = get_object_or_404(Employee, pk=pk)
    devices = employee.devices.all()
    device_task = DeviceTask()

    if not employee.photo:
        logger.warning(f"Employee {employee.last_name} has no photo.")
        return

    try:
        # Process the employee's photo using Thumbor
        base64_image = device_task.process_employee_photo(employee)
    except ValueError as e:
        # Handle exceptions from process_employee_photo without triggering a retry
        logger.error(f"Error processing employee photo for {employee.last_name}: {e}")
        user = employee.created_by
        if user:
            notification = Notification(
                _from=user,
                _to=user,
                redirect=None,
                subject=_(f"Failed to process employee's photo {employee.last_name}"),
                message=str(e),
            )
            notification.save()
        return  # Exit the task without retrying

    try:
        # Send the processed data to each device
        for device in devices:
            device_task.send_to_device(device, employee, base64_image)

        if devices.filter(status='disconnected').exists():
            logger.error(f"Failed to send data to one or more devices for employee {employee.last_name}.")
            raise Exception(_("Failed to send data to one or more devices."))

    except Exception as ex:
        # Handle exceptions from device communication (trigger retry)
        user = employee.created_by
        if user:
            notification = Notification(
                _from=user,
                _to=user,
                redirect=None,
                subject=_(f"Failed to send data for employee {employee.last_name}"),
                message=str(ex),
            )
            notification.save()
        logger.error(f"Error sending data for employee {employee.last_name}: {ex}")
        raise ex  # Re-raise the exception to trigger retry