from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Message, Scenario, Agent
from .retrieval import semantic_query


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


async def build_context(session: AsyncSession, agent: Agent, last_n: int = 20, tz_hint: str | None = None) -> Context:
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

    # Compute availability in agent's (or user-provided) timezone
    tzname = (tz_hint or getattr(agent, "timezone", None) or "UTC")
    try:
        now = datetime.now(ZoneInfo(tzname))
    except Exception:
        now = datetime.now()
    # semantic retrieval over the last user message for enrichment (best-effort)
    q_text = next((m.text or "" for m in reversed(msgs) if m.text and m.role == "user"), "")
    sem = semantic_query(q_text) if q_text else []

    return Context(
        messages=[{"role": m.role, "text": m.text, "image_url": m.image_url, "ts": m.created_at.isoformat()} for m in msgs],
        scenarios=[{"track": s.track, "title": s.title, "progress": s.progress} for s in scs],
        mood=agent.mood,
        availability=_availability(now),
        flags={"romance_allowed": agent.romance_allowed, "semantic": sem, "timezone": tzname},
    )
