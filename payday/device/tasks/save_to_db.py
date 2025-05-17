from django.utils.timezone import now
from device.models import Device, Log
from django.core.cache import cache
from core.utils import set_schema
from django.db import connection
from celery import shared_task
import logging

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
        # make sure the schema exist
        key = f"tenant_{schema.lower()}"
        row = cache.get(key)
        if not row: return

        set_schema(schema)
        cmd = data.get("cmd")

        if not cmd:
            logger.warning(f"Missing 'cmd' key in data: {data}")
            return

        # Register Device
        if cmd in ["reg", "unreg"]:
            status_map = {"reg": "connected", "unreg": "disconnected"}
            status = status_map.get(data.get(cmd, cmd), "disconnected")

            _defaults = {"status": status, "name": data.get("sn", sn)}
            device, created = Device.objects.update_or_create(sn=sn, defaults=_defaults)
            logger.info(f"Device {sn} {'created' if created else 'updated'} with status '{status}'.")

        # Process Bulk Logs from `sendlog`
        elif cmd == "sendlog":
            records = data.get("record", [])
            if not records: return

            # Dynamically fetch the table name from the Django model
            table_name = Log._meta.db_table  

            # Prepare SQL insert statement with conflict handling
            sql = f"""
                INSERT INTO {schema}.{table_name} (sn, timestamp, enroll_id, in_out, mode, event, temperature, verify_mode)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (sn, timestamp, enroll_id, in_out) DO NOTHING;
            """

            values = [
                (
                    sn,
                    record.get("time"),
                    record.get("enrollid"),
                    record.get("inout"),
                    record.get("mode"),
                    record.get("event"),
                    record.get("temp"),
                    record.get("verifymode"),
                )
                for record in records
            ]

            # Execute bulk insert with raw SQL
            with connection.cursor() as cursor:
                cursor.executemany(sql, values)

            logger.info(f"{len(values)} logs inserted for device {sn}, skipping duplicates.")

    except Exception as e:
        logger.error(f"Error processing data for device {sn}: {e}", exc_info=True)
        raise
