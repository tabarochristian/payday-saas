from django.shortcuts import get_object_or_404
from device.tasks import send_to_device
from employee.models import Employee
from core.utils import set_schema
import base64, logging, requests
from celery import shared_task

logger = logging.getLogger(__name__)

def generate_thumbor_url(image_url, host="thumbor", port=8888, width=480, height=640):
    """Generates a Thumbor URL for image processing."""
    base_url = f"http://{host}:{port}/unsafe"
    filters = f"filters:face_detection():crop({width},{height})"
    return f"{base_url}/{width}x{height}/{filters}/{image_url}"

def fetch_image_as_base64(thumbor_url):
    """Fetches processed image and returns it as base64."""
    try:
        response = requests.get(thumbor_url)
        response.raise_for_status()
        return base64.b64encode(response.content).decode("utf-8")
    except requests.RequestException as e:
        logger.error(f"Error fetching image from Thumbor: {e}")
        raise ValueError("Image processing failed.")

def face_detection_crop_using_thumbor_to_base64(image_url, host="thumbor", port=8888, width=480, height=640):
    """Processes an image with Thumbor and returns a base64-encoded string."""
    thumbor_url = generate_thumbor_url(image_url, host, port, width, height)
    return fetch_image_as_base64(thumbor_url)

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=5, max_retries=3)
def send_employee_to_device(schema, pk):
    """Sends employee data to a device with error handling and Celery retries."""
    set_schema(schema)
    employee = get_object_or_404(Employee, pk=pk)

    if not employee.photo:
        logger.warning(f"Employee {employee.pk} has no photo, skipping processing.")
        return

    try:
        # Process the employee's photo using Thumbor
        faced_cropped_base_64 = face_detection_crop_using_thumbor_to_base64(employee.photo.url)
    except ValueError as e:
        logger.error(f"Failed to process employee photo for {employee.last_name}: {e}")
        raise

    devices = employee.devices.all()
    if not devices: return

    sent_to_devices = [
        send_to_device(schema, device.sn, {
            "enrollid": int(employee.registration_number),
            "record": faced_cropped_base_64,
            "name": employee.full_name,
            "cmd": "setuserinfo",
            "sn": device.sn,
            "backupnum": 50
        }) 
        for device in devices
    ]

    return sent_to_devices