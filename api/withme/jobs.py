from __future__ import annotations

from redis import Redis
from rq import Queue

from .config import get_settings


def get_queue(name: str = "default") -> Queue:
    settings = get_settings()
    redis_url = settings.redis_url or "redis://localhost:6379/0"
    conn = Redis.from_url(redis_url)
    return Queue(name, connection=conn)

