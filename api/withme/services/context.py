from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Message, Scenario, Agent


def _availability(now: datetime) -> str:
    # Placeholder timezone: UTC. Windows from PRD.
    hour = now.hour
    if 7 <= hour < 9:
        return "commute"
    if 9 <= hour < 17:
        return "work"
    if 18 <= hour < 23:
        return "evening"
    return "sleep"


@dataclass
class Context:
    messages: list[dict[str, Any]]
    scenarios: list[dict[str, Any]]
    mood: float
    availability: str
    flags: dict[str, Any]


async def build_context(session: AsyncSession, agent: Agent, last_n: int = 20) -> Context:
    # Recency retrieval
    res = await session.execute(
        select(Message)
        .where(Message.agent_id == agent.id)
        .order_by(Message.created_at.desc())
        .limit(last_n)
    )
    msgs = list(reversed(res.scalars().all()))

    # Scenarios (all for now)
    sres = await session.execute(select(Scenario).where(Scenario.agent_id == agent.id).order_by(Scenario.track))
    scs = sres.scalars().all()

    now = datetime.now(timezone.utc)
    return Context(
        messages=[{"role": m.role, "text": m.text, "image_url": m.image_url, "ts": m.created_at.isoformat()} for m in msgs],
        scenarios=[{"track": s.track, "title": s.title, "progress": s.progress} for s in scs],
        mood=agent.mood,
        availability=_availability(now),
        flags={"romance_allowed": agent.romance_allowed},
    )
