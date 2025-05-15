from channels.generic.websocket import AsyncWebsocketConsumer
import json, logging
from datetime import datetime
from .tasks import save_message_to_db
from .redis_pool import redis  # ✅ import shared Redis
from channels.layers import get_channel_layer

logger = logging.getLogger("gateway")

class DeviceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.redis = redis  # ✅ reuse connection pool

    async def disconnect(self, close_code):
        if not hasattr(self, "sn"): return
        await self.channel_layer.group_discard(f"device_{self.sn}", self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data)
            cmd = data.get("cmd")
            sn = data.get("sn")

            if cmd == "reg" and sn:
                self.sn = sn
                await self.channel_layer.group_add(f"device_{sn}", self.channel_name)
                save_message_to_db.delay(sn, text_data, self._schema_from_host())
                await self._flush_queued_commands()
                logger.info(f"🟢 Device registered: {sn}")
            else:
                ack = {
                    "ret": cmd,
                    "result": True,
                    "cloudtime": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                }
                await self.send(text_data=json.dumps(ack))
                save_message_to_db.delay(self.sn, text_data, self._schema_from_host())

        except Exception as e:
            logger.warning(f"❌ Failed to process frame: {e}")

    async def send_command(self, event):
        await self.send(text_data=event["message"])

    async def _flush_queued_commands(self):
        key = f"queue:{self.sn}"
        messages = await self.redis.lrange(key, 0, -1)
        if not messages:
            return

        for msg in messages:
            try:
                await self.send(text_data=msg)
                await self.redis.lpop(key)
            except Exception as e:
                logger.warning(f"❌ Failed to flush command: {e}")
                break

    def _schema_from_host(self):
        headers = dict((k.decode(), v.decode()) for k, v in self.scope["headers"])
        host = headers.get("host", "")
        return host.split(".")[0] if host else "public"
