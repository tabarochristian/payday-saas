# yourapp/redis_pool.py
import redis.asyncio as aioredis
from django.conf import settings

# Shared connection pool for all consumers/views
pool = aioredis.ConnectionPool.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    max_connections=100  # tune this per expected load
)

redis = aioredis.Redis(connection_pool=pool)
