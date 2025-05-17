from django.core.cache import caches
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.conf import settings
from celery import shared_task
import logging, json

logger = logging.getLogger(__name__)  # Configure logging
redis_cache = caches[settings.DEFAULT_CACHE_ALIAS or 'default']  # Configurable cache alias

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=5, max_retries=3)
def send_to_device(self, schema, sn: str, payload: dict):
    """
    Sends a command to the WebSocket group corresponding to a device.

    Parameters:
        schema: Schema of the command (not used in this function but kept for compatibility).
        sn (str): Device serial number.
        payload (dict): Command payload to send.

    Returns:
        dict: JSON response with the execution status.
    """
    try:
        group_name = f"device_{sn}"
        channel_layer = get_channel_layer()
        message = json.dumps({"sn": sn, **payload})

        # Access the underlying Redis client from the cache backend
        redis_client = redis_cache.client.get_client()

        # Check if the device is active in Redis
        try:
            is_active = redis_client.sismember("active_devices", sn)
        except Exception as redis_error:
            logger.error(f"Redis error while checking active devices: {redis_error}")
            return {"status": "error", "message": "Redis connection error"}

        if not is_active:
            try:
                redis_client.rpush(f"queue:{sn}", message)  # Queue message for later processing
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
        logger.error(f"Unexpected error in send_to_device: {e}", exc_info=True)
        return {"status": "error", "message": "Unexpected error occurred"}