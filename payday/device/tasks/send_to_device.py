from django_redis import get_redis_connection
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from celery import shared_task
import logging, json

logger = logging.getLogger(__name__)  # Configure logging
redis_conn = get_redis_connection("default")  # Redis connection

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=5, max_retries=3)
def send_to_device(schema, sn: str, payload: dict):
    """
    Sends a command to the WebSocket group corresponding to a device.

    Parameters:
        request (Request): Incoming HTTP request.
        sn (str): Device serial number.

    Returns:
        Response: JSON response with the execution status.
    """
    try:
        group_name = f"device_{sn}"
        channel_layer = get_channel_layer()
        message = json.dumps({"sn": sn, **payload})

        # Check if the device is active in Redis
        try:
            is_active = redis_conn.sismember("active_devices", sn)
        except Exception as redis_error:
            logger.error(f"Redis error while checking active devices: {redis_error}")
            return {"status": "error", "message": "Redis connection error"}

        if not is_active:
            try:
                redis_conn.rpush(f"queue:{sn}", message)  # Queue message for later processing
                logger.info(f"Device {sn} is inactive. Command queued.")
            except Exception as redis_queue_error:
                logger.error(f"Failed to queue command for {sn}: {redis_queue_error}")
                return {"status": "error", "message": "Failed to queue command"}

            return {"status": "queued"}

        # Send command via WebSocket
        try:
            group_sender = async_to_sync(channel_layer.group_send)
            group_sender(group_name, {"type": "send_command", "message": message})
            logger.info(f"Command sent successfully to {sn} via WebSocket.")
        except Exception as websocket_error:
            logger.error(f"WebSocket error while sending command to {sn}: {websocket_error}")
            return {"status": "error", "message": "WebSocket error"}

        return {"status": "sent"}

    except Exception as e:
        logger.error(f"Unexpected error in push_command: {e}", exc_info=True)
        return {"status": "error", "message": "Unexpected error occurred"}
