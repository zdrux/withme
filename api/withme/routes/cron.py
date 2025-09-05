from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import select

from ..db import session_scope
from ..models import Agent, Event, SemanticMemory
from ..providers.openai_client import OpenAIProvider
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
    if not settings.openai_api_key:
        return {"ok": True, "updated": 0}
    provider = OpenAIProvider()
    async with session_scope() as session:
        res = await session.execute(select(Agent))
        for agent in res.scalars():
            # Very simple semantic refresh: summarize last 20 messages into stable facts
            from .messages import list_messages  # avoid circular imports at module import
            # Instead of calling the route, query directly
            msgs_res = await session.execute(
                select(Event)
            )
            # Build a small prompt using recent context via messages table
            from sqlalchemy import select as _select
            from ..models import Message
            r = await session.execute(
                _select(Message).where(Message.agent_id == agent.id).order_by(Message.created_at.desc()).limit(20)
            )
            texts = []
            for m in reversed(r.scalars().all()):
                if m.text:
                    texts.append(f"{m.role}: {m.text}")
            convo = "\n".join(texts)
            if not convo:
                continue
            sys = "Summarize stable facts/preferences learned from this conversation in 3-5 bullets."
            summary = provider.chat(sys, [{"role": "user", "content": convo}])
            mem = SemanticMemory(agent_id=agent.id, content=summary)
            session.add(mem)
            updated += 1
    return {"ok": True, "updated": updated}
