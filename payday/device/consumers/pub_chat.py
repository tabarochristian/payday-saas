from datetime import datetime
import logging
import json
import re
from typing import Dict, Optional

from channels.generic.websocket import WebsocketConsumer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.core.cache import caches
from django.conf import settings
from device.tasks import save_to_db

logger = logging.getLogger("gateway")
channel_layer = get_channel_layer()
redis_cache = caches[settings.DEFAULT_CACHE_ALIAS or 'default']  # Configurable cache alias

class PubChat(WebsocketConsumer):
    """WebSocket consumer for handling device communication with tenant-based schema."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.schema: str = settings.DEFAULT_SCHEMA  # Configurable default schema
        self.sn: Optional[str] = None

    def connect(self) -> None:
        """Handle WebSocket connection establishment."""
        self.accept()
        self.schema = self._schema_from_host()
        logger.info(f"🔌 New WebSocket connection established for schema: {self.schema}")

        if not self._schema_exists():
            logger.warning(f"🚫 Unknown schema '{self.schema}' — disconnecting.")
            self.close()
            return

    def disconnect(self, close_code: int) -> None:
        """Handle WebSocket disconnection and cleanup."""
        if not self.sn:
            logger.debug("🔌 No device SN set; skipping disconnect cleanup.")
            return

        try:
            async_to_sync(channel_layer.group_discard)(f"device_{self.sn}", self.channel_name)
            redis_client = redis_cache.client.get_client()
            redis_client.srem("active_devices", self.sn)  # Remove from active devices set
            save_to_db.delay(self.schema, self.sn, {"sn": self.sn, "cmd": "unreg"})
            logger.info(f"🔴 Device disconnected: {self.sn}")
        except Exception as e:
            logger.error(f"❌ Failed to clean up device {self.sn}: {e}")

    def _schema_exists(self) -> bool:
        """Check if the tenant schema exists in Redis."""
        try:
            return bool(redis_cache.get(f"tenant_{self.schema.lower()}"))
        except Exception as e:
            logger.error(f"❌ Redis error checking schema {self.schema}: {e}")
            return False

    def receive(self, text_data: Optional[str] = None, bytes_data: Optional[bytes] = None) -> None:
        """Handle incoming WebSocket messages."""
        if not text_data:
            logger.warning("⚠️ Received empty message.")
            return

        try:
            data = json.loads(text_data)
            cmd = data.get("cmd")
            sn = data.get("sn")

            if not cmd or not sn:
                raise ValueError("Missing 'cmd' or 'sn' in message")

            if not self.sn:
                self.sn = sn
            elif self.sn != sn:
                logger.warning(f"⚠️ Mismatched SN: expected {self.sn}, got {sn}")
                return

            if cmd == "reg":
                self._register_device(sn)
                async_to_sync(channel_layer.group_add)(f"device_{sn}", self.channel_name)
                self._flush_queued_commands()

            ack = {
                "ret": cmd,
                "result": True,
                "schema": self.schema,
                "cloudtime": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            }
            self.send(text_data=json.dumps(ack))
            save_to_db.delay(self.schema, sn, data)

        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in message: {e}")
            self._send_error("Invalid JSON format")
        except ValueError as e:
            logger.warning(f"⚠️ Validation error: {e}")
            self._send_error(str(e))
        except Exception as e:
            logger.exception(f"❌ Unexpected error processing message: {e}")
            self._send_error("Internal server error")

    def send_command(self, event: Dict) -> None:
        """Send a command to the client."""
        message = event.get("message")
        if not message:
            logger.debug("⚠️ Empty message in send_command.")
            return
        try:
            self.send(text_data=message)
        except Exception as e:
            logger.warning(f"❌ Failed to send command to {self.sn}: {e}")

    def _register_device(self, sn: str) -> None:
        """Register a device in Redis."""
        try:
            redis_client = redis_cache.client.get_client()
            redis_client.sadd("active_devices", sn)  # Add to active devices set
            logger.info(f"🟢 Device registered: {sn}")
        except Exception as e:
            logger.error(f"❌ Failed to register device {sn}: {e}")
            raise

    def _flush_queued_commands(self) -> None:
        """Send queued commands to the device and clear the queue."""
        key = f"queue:{self.sn}"
        try:
            redis_client = redis_cache.client.get_client()
            messages = redis_client.lrange(key, 0, -1)  # Get all queued messages
            if not messages:
                return

            logger.info(f"📤 Flushing {len(messages)} queued commands for {self.sn}")
            messages = [msg.decode() for msg in messages]
            with redis_client.pipeline() as pipe:
                for msg in messages:
                    self.send(text_data=msg)
                pipe.delete(key)
                pipe.execute()
        except Exception as e:
            logger.error(f"❌ Failed to flush queue for {self.sn}: {e}")

    def _schema_from_host(self) -> str:
        """Extract tenant schema from host header."""
        try:
            headers = {k.decode(): v.decode() for k, v in self.scope.get("headers", [])}
            host = headers.get("host", "")
            if not host:
                logger.debug("⚠️ No host header found; using default schema.")
                return settings.DEFAULT_SCHEMA

            schema = host.split(".")[0]
            if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", schema):
                return schema
            logger.warning(f"⚠️ Invalid schema pattern extracted: {schema}")
            return settings.DEFAULT_SCHEMA
        except Exception as e:
            logger.warning(f"⚠️ Failed to extract schema from headers: {e}")
            return settings.DEFAULT_SCHEMA

    def _send_error(self, message: str) -> None:
        """Send an error message to the client."""
        try:
            error_msg = {"ret": "error", "result": False, "message": message}
            self.send(text_data=json.dumps(error_msg))
        except Exception as e:
            logger.warning(f"❌ Failed to send error message: {e}")