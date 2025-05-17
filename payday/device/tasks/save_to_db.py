from django.utils.timezone import now
from device.models import Device, Log
from django.core.cache import cache
from core.utils import set_schema
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
            log_index = data.get("logindex", now())
            records = data.get("record", [])

            records = [
                Log(
                    sn=sn,
                    enroll_id=record.get("enrollid"),
                    timestamp=record.get("time"),
                    mode=record.get("mode"),

                    in_out=record.get("inout"),
                    event=record.get("event"),
                    
                    temperature=record.get("temp"),
                    verify_mode=record.get("verifymode")
                )
                for record in records
            ]

            if not records: return
            Log.objects.bulk_create(records, ignore_conflicts=True)
            logger.info(f"{len(records)} logs created for device {sn}.")

    except Exception as e:
        logger.error(f"Error processing data for device {sn}: {e}", exc_info=True)
        raise
