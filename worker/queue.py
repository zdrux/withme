from __future__ import annotations

from dataclasses import dataclass

try:
    import redis  # type: ignore
    from rq import Queue  # type: ignore
except Exception:  # pragma: no cover - optional
    redis = None
    Queue = None


@dataclass
class RQContext:
    redis_url: str

    def get_queue(self, name: str = "default"):
        if redis is None or Queue is None:
            raise RuntimeError("RQ/redis not installed; cannot create queue")
        conn = redis.from_url(self.redis_url)
        return Queue(name, connection=conn)

