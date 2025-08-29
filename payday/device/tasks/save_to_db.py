from django.utils.timezone import now
from device.models import Device, Log
from django.core.cache import cache
from core.utils import set_schema
from django.db import connection
from celery import shared_task
import logging
import re

logger = logging.getLogger(__name__)

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=5, max_retries=3)
def save_to_db(self, schema: str, sn: str, data: dict) -> None:
    """
    Saves device messages to the database with bulk creation and update logic.

    Parameters:
        schema (str): Database schema name.
        sn (str): Device serial number.
        data (dict): Received data payload.

    Returns:
        None
    """
    try:
        # Validate schema name to prevent SQL injection
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", schema):
            logger.error(f"🚫 Invalid schema name: '{schema}'")
            return

        key = f"tenant_{schema.lower()}"
        tenant = cache.get(key)
        if not tenant:
            logger.warning(f"⛔ Tenant schema '{schema}' not found in cache.")
            return

        set_schema(schema)
        cmd = data.get("cmd")
        if not cmd:
            logger.warning(f"⚠️ Missing 'cmd' in data: {data}")
            return

        # Register or unregister device
        if cmd in ["reg", "unreg"]:
            status_map = {"reg": "connected", "unreg": "disconnected"}
            status = status_map.get(cmd, "disconnected")

            device, created = Device.objects.get_or_create(
                sn=sn,
                defaults={
                    "status": status,
                    "name": data.get("name", sn),
                }
            )

            if not created:
                device.status = status
                device.save(update_fields=["status"])

            logger.info(f"✅ Device '{sn}' {'created' if created else 'updated'} with status '{status}'.")

        # Bulk log insert
        elif cmd == "sendlog":
            records = data.get("record", [])
            if not records:
                logger.info(f"📭 No log records to insert for device {sn}")
                return

            values = [Log(
                sn=sn,
                _metadata=record,
                enroll_id=record.get("enrollid"),
                timestamp=record.get("time"),
                in_out=record.get("inout"),
                mode=record.get("mode"),
                event=record.get("event"),
                temperature=record.get("temp"),
                verify_mode=record.get("verifymode")
            ) for record in records]
            Log.objects.bulk_create(values, ignore_conflicts=True)

            logger.info(f"📦 Inserted {len(values)} logs for device {sn}, skipped duplicates.")

    except Exception as e:
        logger.error(f"💥 Error processing data for device '{sn}' in schema '{schema}': {e}", exc_info=True)
        raise
