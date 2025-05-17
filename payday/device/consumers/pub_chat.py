from datetime import datetime
import logging
import json

from channels.generic.websocket import WebsocketConsumer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.core.cache import caches
from device.tasks import save_to_db

logger = logging.getLogger("gateway")
channel_layer = get_channel_layer()
redis_cache = caches["default"]  # Sync Redis backend


class PubChat(WebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.schema = "public"
        self.sn = None

    def connect(self):
        self.accept()
        logger.info("🔌 New WebSocket connection established.")

    def disconnect(self, close_code):
        if not self.sn:
            return

        try:
            async_to_sync(channel_layer.group_discard)(f"device_{self.sn}", self.channel_name)
        except Exception as e:
            logger.warning(f"❌ Failed to discard from group {self.sn}: {e}")

        try:
            redis_cache.delete(f"active_device:{self.sn}")
            save_to_db.delay(self.schema, self.sn, {
                "sn": self.sn,
                "cmd": "unreg"
            })
            logger.info(f"🔴 Device disconnected: {self.sn}")
        except Exception as e:
            logger.error(f"❌ Failed to remove device from Redis: {e}")

    def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data)
            cmd = data.get("cmd")
            sn = data.get("sn")

            if not cmd or not sn:
                raise ValueError("Missing 'cmd' or 'sn' in message")

            self.schema = self._schema_from_host()
            self.sn = sn

            if cmd == "reg":
                self._register_device(sn)
                add_to_group = async_to_sync(channel_layer.group_add)
                add_to_group(f"device_{sn}", self.channel_name)
                self._flush_queued_commands()

            ack = {
                "ret": cmd,
                "result": True,
                "schema": self.schema,
                "cloudtime": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            }
            self.send(text_data=json.dumps(ack))
            save_to_db.delay(self.schema, sn, data)

        except Exception as e:
            logger.exception(f"❌ Error processing message: {e}")

    def send_command(self, event):
        message = event.get("message")
        if not message:
            return
        try:
            self.send(text_data=message)
        except Exception as e:
            logger.warning(f"❌ Failed to send queued command: {e}")

    def _register_device(self, sn: str):
        try:
            redis_cache.set(f"active_device:{sn}", True, timeout=None)
            logger.info(f"🟢 Device registered: {sn}")
        except Exception as e:
            logger.error(f"❌ Failed to register device {sn}: {e}")

    def _flush_queued_commands(self):
        key = f"queue:{self.sn}"
        try:
            messages = redis_cache.get(key) or []
            if not isinstance(messages, list):
                logger.warning(f"⚠️ Unexpected data in queue for {self.sn}, resetting queue.")
                messages = []

            if not messages:
                return

            logger.info(f"📤 Flushing {len(messages)} queued commands for {self.sn}")
            for msg in messages:
                self.send(text_data=msg)

            redis_cache.delete(key)
        except Exception as e:
            logger.error(f"❌ Error flushing queue for {self.sn}: {e}")

    def _schema_from_host(self) -> str:
        try:
            headers = {}
            for k, v in self.scope["headers"]:
                try:
                    headers[k.decode()] = v.decode()
                except UnicodeDecodeError:
                    continue
            host = headers.get("host", "")
            if host:
                return host.split(".")[0]
            return "public"
        except Exception as e:
            logger.warning(f"⚠️ Failed to extract schema from host: {e}")
            return "public"
