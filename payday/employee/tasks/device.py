import os
import logging
import requests
import json
import numpy as np
import base64
import cv2
from django.utils.translation import gettext as _
from django.shortcuts import get_object_or_404
from django.conf import settings
from employee.models import Employee
from core.models import Notification
from celery import shared_task
from core.utils import set_schema

logger = logging.getLogger(__name__)

class DeviceTask:
    """
    A helper class to handle image processing and device communication.
    """

    def __init__(self):
        # Load the pre-trained face detection model once during initialization
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )

    def fetch_image(self, image_url):
        """
        Fetch an image from a URL and convert it to a numpy array.
        """
        try:
            response = requests.get(image_url)
            response.raise_for_status()
            image_array = np.asarray(bytearray(response.content), dtype=np.uint8)
            return cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        except requests.RequestException as e:
            logger.error(f"Failed to fetch image from URL: {image_url}. Error: {e}")
            raise ValueError(_("Failed to fetch the image from the URL."))

    def crop_face(self, image):
        """
        Detect and crop the largest face in the image to 480x640 pixels.
        """
        if image.shape[0] < 640 or image.shape[1] < 480:
            logger.error("Image is below the required size of 480x640.")
            raise ValueError(_("Image is below the required size of 480x640."))

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
        )

        if len(faces) == 0:
            logger.error("No face detected in the image.")
            raise ValueError(_("No face detected in the image."))

        (x, y, w, h) = max(faces, key=lambda f: f[2] * f[3])
        center_x = x + w // 2
        center_y = y + h // 2
        start_x = max(center_x - 240, 0)
        start_y = max(center_y - 320, 0)
        end_x = min(start_x + 480, image.shape[1])
        end_y = min(start_y + 640, image.shape[0])
        start_x = end_x - 480
        start_y = end_y - 640

        cropped_image = image[start_y:end_y, start_x:end_x]

        if cropped_image.shape[0] != 640 or cropped_image.shape[1] != 480:
            logger.error("Failed to crop the image to the required size of 480x640.")
            raise ValueError(_("Failed to crop the image to the required size of 480x640."))

        return cropped_image

    def encode_image_to_base64(self, image):
        """
        Encode an image to a base64 string.
        """
        _, buffer = cv2.imencode('.jpg', image)
        return base64.b64encode(buffer).decode('utf-8')

    def process_employee_photo(self, employee):
        """
        Process the employee's photo to detect and crop the face.
        """
        if not employee.photo:
            logger.error(f"Employee {employee.full_name} has no photo.")
            raise ValueError(_("Employee has no photo."))

        image = self.fetch_image(employee.photo.url)
        cropped_image = self.crop_face(image)
        return self.encode_image_to_base64(cropped_image)

    def send_to_device(self, device, employee, base64_image):
        """
        Send employee data and base64 image to the device.
        """
        try:
            print({
                "sn": device.sn,
                "cmd": "setuserinfo",
                "enrollid": int(employee.registration_number),
                "name": employee.full_name,
                "backupnum": 50,
                "record": base64_image,
            })
            response = requests.post(
                "http://46.101.92.215:7788/send-command/",
                json={
                    "sn": device.sn,
                    "cmd": "setuserinfo",
                    "enrollid": int(employee.registration_number),
                    "name": employee.full_name,
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
    """
    set_schema(tenant)
    employee = get_object_or_404(Employee, pk=pk)
    devices = employee.devices.all()
    device_task = DeviceTask()

    if not employee.photo:
        logger.warning(f"Employee {employee.full_name} has no photo.")
        return

    try:
        # Process the employee's photo
        base64_image = device_task.process_employee_photo(employee)
    except ValueError as e:
        # Handle exceptions from process_employee_photo without triggering a retry
        logger.error(f"Error processing employee photo for {employee.full_name}: {e}")
        user = employee.created_by
        if user:
            notification = Notification(
                _from=user,
                _to=user,
                redirect=None,
                subject=_(f"Failed to process employee's photo {employee.full_name}"),
                message=str(e),
            )
            notification.save()
        return  # Exit the task without retrying

    try:
        # Send the processed data to each device
        for device in devices:
            device_task.send_to_device(device, employee, base64_image)

        if devices.filter(status='disconnected').exists():
            logger.error(f"Failed to send data to one or more devices for employee {employee.full_name}.")
            raise Exception(_("Failed to send data to one or more devices."))

    except Exception as ex:
        # Handle exceptions from device communication (trigger retry)
        user = employee.created_by
        if user:
            notification = Notification(
                _from=user,
                _to=user,
                redirect=None,
                subject=_(f"Failed to send data for employee {employee.full_name}"),
                message=str(ex),
            )
            notification.save()
        logger.error(f"Error sending data for employee {employee.full_name}: {ex}")
        raise ex  # Re-raise the exception to trigger retry