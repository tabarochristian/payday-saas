"""
High-performance protocol gateway
---------------------------------
* WebSocket  : /pub/chat      – devices connect here
* HTTP POST  : /api/device/{sn}/command  – backend pushes commands to a device
"""

import asyncio, json, logging, os
from datetime import datetime
from typing import Dict, Any

import redis.asyncio as aioredis
from redis.asyncio import Redis
import uvicorn

from fastapi import Depends, FastAPI, HTTPException, Path, WebSocket, WebSocketDisconnect
from fastapi.background import BackgroundTasks
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from typing import Literal

from tasks import save_message_to_db  # Celery task

# --------------------------------------------------------------------------- #
#  App & infrastructure
# --------------------------------------------------------------------------- #
load_dotenv()
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
logger = logging.getLogger("gateway")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(title="Device WebSocket Gateway – v2.4")

redis: aioredis.Redis | None = None
connected: Dict[str, WebSocket] = {}  # {sn: WebSocket}

async def get_redis() -> aioredis.Redis:
    return redis  # type: ignore

@app.on_event("startup")
async def _startup() -> None:
    global redis
    redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    logger.info("✅ Redis connected → %s", REDIS_URL)

@app.on_event("shutdown")
async def _shutdown() -> None:
    await redis.close()  # type: ignore
    logger.info("🛑 Redis connection closed")

# --------------------------------------------------------------------------- #
#  Data models
# --------------------------------------------------------------------------- #
class DeviceRegistration(BaseModel):
    cmd: str = Literal["reg"]
    sn: str

class GenericFrame(BaseModel):
    cmd: str
    sn: str
    data: dict | None = None

class Ack(BaseModel):
    ret: str
    result: bool = True
    cloudtime: str = Field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))

class Command(BaseModel):
    cmd: str
    payload: Dict[str, Any] | None = None

# --------------------------------------------------------------------------- #
#  WebSocket – device handshake + messages
# --------------------------------------------------------------------------- #
@app.websocket("/pub/chat")
async def ws_device_endpoint(sock: WebSocket,
                             redis_conn: aioredis.Redis = Depends(get_redis)) -> None:
    await sock.accept()

    try:
        reg_raw = await sock.receive_text()
        reg = DeviceRegistration.model_validate_json(reg_raw)
    except Exception:
        await sock.close(code=4000, reason="Invalid registration payload")
        return

    sn = reg.sn
    if sn in connected:
        await connected[sn].close(code=4001, reason="Duplicate connection")
    connected[sn] = sock
    logger.info("🟢 Registered device: %s", sn)

    save_message_to_db.delay(sn, reg_raw, schema_name=_schema_from_host(sock))

    # ---- progressive flush of queued commands ---- #
    key = f"queue:{sn}"

    while True:
        # Peek at the first message in the queue without removing it
        cmd = await redis_conn.lindex(key, 0)
        if cmd is None:
            break  # Queue is empty

        try:
            await sock.send_text(cmd)
            await redis_conn.lpop(key)  # Remove only after successful send
            logger.info("➡️ Sent queued message to %s: %s", sn, cmd)
        except Exception as e:
            logger.warning("❌ Failed to send to %s, stopping replay: %s", sn, e)
            break  # Stop processing if connection is unstable


    # ---- message loop ---- #
    try:
        while True:
            raw = await sock.receive_text()
            logger.debug("⬅️  %s → %s", sn, raw)

            try:
                frame = GenericFrame.model_validate_json(raw)
                await sock.send_text(Ack(ret=frame.cmd).model_dump_json())
            except Exception as e:
                logger.warning("❗ Invalid JSON or ACK failure for %s: %s", sn, e)

            save_message_to_db.delay(sn, raw, _schema_from_host(sock))

    except WebSocketDisconnect:
        logger.warning("🔴 Device %s disconnected", sn)
    finally:
        connected.pop(sn, None)

# --------------------------------------------------------------------------- #
#  HTTP – backend issues command to device
# --------------------------------------------------------------------------- #
@app.post("/api/device/{sn}/command", status_code=202)
async def push_command(
        cmd: Command,
        bg: BackgroundTasks,
        sn: str = Path(...),
        redis_conn: Redis = Depends(get_redis),  # ✅ now this works
    ) -> dict:
    """
    Forward a command to a connected device. If offline, queue it in Redis.
    """
    payload = cmd.model_dump()
    message = json.dumps({"sn": sn, **payload})

    if socket := connected.get(sn):
        try:
            await socket.send_text(message)
            logger.info("➡️  Command sent to %s: %s", sn, payload["cmd"])
        except Exception as e:
            logger.warning("❌ Send failed, queuing instead: %s", e)
            await redis_conn.rpush(f"queue:{sn}", message)
    else:
        await redis_conn.rpush(f"queue:{sn}", message)
        logger.info("💤 Device offline – queued command for %s", sn)

    bg.add_task(save_message_to_db.delay, sn, message, _schema_from_sn(sn))
    return {"status": "queued" if sn not in connected else "sent"}

# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #
def _schema_from_host(sock: WebSocket) -> str:
    """
    Extracts schema name from subdomain of host header.
    Assumes format: [subdomain].[domain].[tld], e.g., acme.example.com → 'acme'
    """
    host = sock.headers.get("host", None)
    if not host:
        return "public"

    # Remove port if present
    host = host.split(":")[0]
    parts = host.split(".")
    return parts[0] or "public"


def _schema_from_sn(sn: str) -> str:
    """
    Fallback mapping from serial number (sn) if no host info is available.
    """
    return "public" if "_" not in sn else sn.split("_", 1)[0]

# --------------------------------------------------------------------------- #
#  Dev entry-point
# --------------------------------------------------------------------------- #
# if __name__ == "__main__":
#     uvicorn.run("server:app", host="0.0.0.0", port=7788, reload=False)
