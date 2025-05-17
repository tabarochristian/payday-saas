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

            _defaults = {
                "status": status,
                "name": data.get("sn", sn),
            }

            device, created = Device.objects.update_or_create(sn=sn, defaults=_defaults)
            logger.info(f"✅ Device '{sn}' {'created' if created else 'updated'} with status '{status}'.")

        # Bulk log insert
        elif cmd == "sendlog":
            records = data.get("record", [])
            if not records:
                logger.info(f"📭 No log records to insert for device {sn}")
                return

            table_name = Log._meta.db_table

            sql = f"""
                INSERT INTO {schema}.{table_name}
                    (sn, timestamp, enroll_id, in_out, mode, event, temperature, verify_mode)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (sn, timestamp, enroll_id, in_out) DO NOTHING;
            """

            values = [(
                sn,
                record.get("time"),  # Ensure this is a UTC or naive UTC timestamp
                record.get("enrollid"),
                record.get("inout"),
                record.get("mode"),
                record.get("event"),
                record.get("temp"),
                record.get("verifymode"),
            ) for record in records]

            with connection.cursor() as cursor:
                cursor.executemany(sql, values)

            logger.info(f"📦 Inserted {len(values)} logs for device {sn}, skipped duplicates.")

    except Exception as e:
        logger.error(f"💥 Error processing data for device '{sn}' in schema '{schema}': {e}", exc_info=True)
        raise
