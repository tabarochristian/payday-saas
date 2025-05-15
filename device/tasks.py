import asyncio, json, logging, os
from typing import Any

import asyncpg
from celery import Celery
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("tasks")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://postgres:pass@db:5432/messages_db")
BROKER_URL   = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery = Celery("device-task", broker=BROKER_URL)

class _DB:
    pool: asyncpg.Pool | None = None

    @classmethod
    async def pool_async(cls) -> asyncpg.Pool:
        if cls.pool is None:
            cls.pool = await asyncpg.create_pool(POSTGRES_URL, min_size=2, max_size=10)
            logger.info("PostgreSQL pool ready")
        return cls.pool

async def _upsert(sn: str, raw: str, schema: str) -> None:
    pool = await _DB.pool_async()
    async with pool.acquire() as conn:
        print("Saved")
        #await conn.execute(f"""
        #    INSERT INTO {schema}.messages (sn, message, ts)
        #    VALUES ($1, $2, CURRENT_TIMESTAMP)
        #    ON CONFLICT (sn, message)
        #    DO UPDATE SET ts = EXCLUDED.ts;
        #""", sn, raw)

@celery.task(bind=True, autoretry_for=(Exception,), max_retries=5,
             retry_backoff=True, retry_backoff_max=300)
def save_message_to_db(self, sn: str, raw: str, schema_name: str) -> None:
    """
    Celery entry-point – runs inside a worker process.
    """
    try:
        asyncio.run(_upsert(sn, raw, schema_name))
    except Exception as e:
        logger.exception("DB write failed")
        raise self.retry(exc=e)
