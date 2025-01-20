from django.utils.translation import gettext as _
from django.shortcuts import get_object_or_404
from django.conf import settings
import os, requests, json

from employee.models import Employee
from core.models import Notification
from celery import shared_task

import numpy as np
import base64
import cv2

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
        response = requests.get(image_url)
        if response.status_code != 200:
            raise ValueError(_("Failed to fetch the image from the URL."))
        image_array = np.asarray(bytearray(response.content), dtype=np.uint8)
        return cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    def crop_face(self, image):
        """
        Detect and crop the largest face in the image to 480x640 pixels.
        """
        # Check if the image is below the required size
        if image.shape[0] < 640 or image.shape[1] < 480:
            raise ValueError(_("Image is below the required size of 480x640."))

        # Convert to grayscale for face detection
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Detect faces in the image
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
        )

        if len(faces) == 0:
            raise ValueError(_("No face detected in the image."))

        # Assume the largest face is the main face
        (x, y, w, h) = max(faces, key=lambda f: f[2] * f[3])

        # Calculate the center of the face
        center_x = x + w // 2
        center_y = y + h // 2

        # Calculate the top-left corner of the 480x640 crop
        start_x = max(center_x - 240, 0)
        start_y = max(center_y - 320, 0)

        # Ensure the crop does not go out of the image boundaries
        end_x = min(start_x + 480, image.shape[1])
        end_y = min(start_y + 640, image.shape[0])

        # Adjust start positions if the end positions are at the boundary
        start_x = end_x - 480
        start_y = end_y - 640

        # Crop the image
        cropped_image = image[start_y:end_y, start_x:end_x]

        # Check if the cropped image is of the correct size
        if cropped_image.shape[0] != 640 or cropped_image.shape[1] != 480:
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
            raise ValueError(_("Employee has no photo."))

        # Fetch the image from the URL
        image = self.fetch_image(employee.photo.url)

        # Crop the face
        cropped_image = self.crop_face(image)

        # Encode the cropped image to base64
        return self.encode_image_to_base64(image)

    def send_to_device(self, device, employee, base64_image):
        """
        Send employee data and base64 image to the device.
        """
        try:
            response = requests.post(
                "http://device:7788/send-command/",
                data={
                    "sn": device.sn,
                    "cmd": "setuserinfo",
                    "enrollid": employee.registration_number,
                    "name": employee.full_name,
                    "backupnum": 50,
                    "record": base64_image,
                },
            )
            response.raise_for_status()  # Raise an exception for HTTP errors
        except requests.RequestException as ex:
            raise ex  # Re-raise the exception to trigger retry


@shared_task(
    bind=True,
    autoretry_for=(requests.RequestException, ValueError, Exception),
    retry_kwargs={'max_retries': 3, 'countdown': 5}
)
def setuserinfo(self, pk, *args, **kwargs):
    """
    Celery task to process an employee's photo and send it to associated devices.
    """
    device_task = DeviceTask()
    employee = get_object_or_404(Employee, pk=pk)
    devices = employee.devices.all()

    if not employee.photo:
        return

    try:
        # Process the employee's photo
        base64_image = device_task.process_employee_photo(employee)

        # Send the processed data to each device
        for device in devices:
            device_task.send_to_device(device, employee, base64_image)

    except Exception as ex:
        # Handle exceptions (e.g., log and notify)
        user = employee.created_by
        if not user:
            return

        notification = Notification(
            _from=user,
            _to=user,
            redirect=None,
            subject=_(f"Failed to process employee {employee.full_name}"),
            message=str(ex),
        )
        notification.save()

        # Re-raise the exception to trigger retry or fail the task
        raise ex