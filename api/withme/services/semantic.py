from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Agent, Message, SemanticMemory
from ..providers.openai_client import OpenAIProvider
from .retrieval import ensure_embedding


async def _summarize_recent(session: AsyncSession, agent: Agent, max_messages: int = 20) -> Optional[str]:
    """Summarize stable facts/preferences from recent conversation, or None.

    Uses OpenAI if configured; otherwise returns None.
    """
    from ..config import get_settings

    settings = get_settings()
    if not settings.openai_api_key:
        return None
    res = await session.execute(
        select(Message)
        .where(Message.agent_id == agent.id)
        .order_by(Message.created_at.desc())
        .limit(max_messages)
    )
    msgs = list(reversed(res.scalars().all()))
    if not msgs:
        return None
    texts: list[str] = []
    for m in msgs:
        if m.text:
            texts.append(f"{m.role}: {m.text}")
    convo = "\n".join(texts)
    if not convo:
        return None
    provider = OpenAIProvider()
    system = "Summarize stable facts and preferences learned since last update. Output 3-5 bullet points."
    out = provider.chat(system, [{"role": "user", "content": convo}])
    return out.strip() if out else None


async def maybe_update_semantic_memory(
    session: AsyncSession,
    agent: Agent,
    min_interval_hours: int = 6,
) -> bool:
    """Insert a new SemanticMemory row if the last update is older than interval.

    Also ensures the latest memory is embedded into Pinecone if configured.
    Returns True if an update occurred.
    """
    res = await session.execute(
        select(SemanticMemory)
        .where(SemanticMemory.agent_id == agent.id)
        .order_by(SemanticMemory.updated_at.desc())
        .limit(1)
    )
    last = res.scalars().first()
    now = datetime.now(timezone.utc)
    if last and (now - last.updated_at) < timedelta(hours=min_interval_hours):
        return False
    summary = await _summarize_recent(session, agent)
    if not summary:
        return False
    mem = SemanticMemory(agent_id=agent.id, content=summary, updated_at=now)
    session.add(mem)
    # Flush so ensure_embedding can read it if needed
    await session.flush()
    try:
        await ensure_embedding(session, agent)
    except Exception:
        # Best effort; embedding may be unavailable in dev
        pass
    return True

