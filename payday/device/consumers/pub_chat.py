from channels.generic.websocket import AsyncWebsocketConsumer
import json, logging
from datetime import datetime
from .tasks import save_message_to_db
from .redis_pool import redis  # ✅ import shared Redis
from channels.layers import get_channel_layer

logger = logging.getLogger("gateway")

class PubChat(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.redis = redis  # ✅ reuse connection pool
        self.sn = None  # Initialize sn

    async def disconnect(self, close_code):
        if not self.sn:
            return

        # Remove from Channels group
        await self.channel_layer.group_discard(f"device_{self.sn}", self.channel_name)
        
        # Remove device SN from Redis set of active devices
        try:
            await self.redis.srem("active_devices", self.sn)
            logger.info(f"🔴 Device disconnected and removed from active list: {self.sn}")
        except Exception as e:
            logger.warning(f"❌ Failed to remove device from active list: {e}")

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data)
            cmd = data.get("cmd")
            sn = data.get("sn")

            if not cmd or not sn:
                logger.warning(f"❌ Failed to process frame: {e}")
                raise Exception("unknow message")

            if cmd == "reg" and sn:
                self.sn = sn

                # Add device SN to Redis set of active devices
                try:
                    await self.redis.sadd("active_devices", sn)
                    logger.info(f"🟢 Device added to active list: {sn}")
                except Exception as e:
                    logger.warning(f"❌ Failed to add device to active list: {e}")

                await self.channel_layer.group_add(f"device_{sn}", self.channel_name)
                logger.info(f"🟢 Device registered: {sn}")
                await self._flush_queued_commands()

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
        return headers.get("host", "").split(".")[0] if host else "public"
