import redis
from app.config import settings

# Global redis client for health checks
# Note: Celery uses its own internal client, but we use this for the /health endpoint
redis_client = redis.from_url(settings.redis_url, decode_responses=True)
