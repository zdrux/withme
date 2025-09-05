from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import select

from ..db import session_scope
from ..models import Agent, Event
from ..services.semantic import maybe_update_semantic_memory
from ..config import get_settings


router = APIRouter()


def _authorized(internal_token: str | None, header_token: str | None) -> bool:
    return bool(internal_token) and header_token == f"Bearer {internal_token}"


@router.post("/daily_event")
async def daily_event(authorization: str | None = Header(default=None)):
    settings = get_settings()
    internal_token = settings.cron_token
    if not _authorized(internal_token, authorization):
        raise HTTPException(status_code=403, detail="Forbidden")
    count = 0
    async with session_scope() as session:
        res = await session.execute(select(Agent))
        for agent in res.scalars():
            import random

            if random.random() <= 0.05:  # 5% chance per PRD
                mood_delta = random.choice([-0.1, -0.05, 0.05, 0.1, 0.2])
                ev = Event(
                    agent_id=agent.id,
                    type="daily",
                    payload_json={"summary": "Random daily event"},
                    mood_delta=mood_delta,
                    seed=random.getrandbits(32),
                )
                session.add(ev)
                agent.mood = max(-1.0, min(1.0, (agent.mood or 0.0) + mood_delta))
                count += 1
    return {"ok": True, "events": count}


@router.post("/semantic_refresh")
async def semantic_refresh(authorization: str | None = Header(default=None)):
    settings = get_settings()
    internal_token = settings.cron_token
    if not _authorized(internal_token, authorization):
        raise HTTPException(status_code=403, detail="Forbidden")
    updated = 0
    async with session_scope() as session:
        res = await session.execute(select(Agent))
        for agent in res.scalars():
            try:
                ok = await maybe_update_semantic_memory(session, agent, min_interval_hours=24)
                if ok:
                    updated += 1
            except Exception:
                pass
    return {"ok": True, "updated": updated}
