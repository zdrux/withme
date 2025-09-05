from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import SemanticMemory, Agent
from ..providers.openai_client import OpenAIProvider
from ..config import get_settings

try:
    from pinecone import Pinecone  # type: ignore[import-untyped]
except Exception:  # pragma: no cover
    Pinecone = None  # type: ignore


INDEX_NAME = "withme-semantic"


async def ensure_embedding(session: AsyncSession, agent: Agent, provider: Optional[OpenAIProvider] = None) -> None:
    # Example: embed the latest semantic memory into Pinecone (no-op if not configured)
    settings = get_settings()
    if not settings.pinecone_api_key or Pinecone is None or not settings.openai_api_key:
        return
    res = await session.execute(
        select(SemanticMemory).where(SemanticMemory.agent_id == agent.id).order_by(SemanticMemory.updated_at.desc()).limit(1)
    )
    mem = res.scalars().first()
    if not mem:
        return
    provider = provider or OpenAIProvider()
    vec = provider.embed([mem.content])[0]
    pc = Pinecone(api_key=settings.pinecone_api_key)
    if INDEX_NAME not in [i.name for i in pc.list_indexes()]:  # type: ignore[attr-defined]
        pc.create_index(name=INDEX_NAME, dimension=len(vec), metric="cosine")  # type: ignore[attr-defined]
    index = pc.Index(INDEX_NAME)  # type: ignore[attr-defined]
    index.upsert(vectors=[{"id": f"{agent.id}", "values": vec, "metadata": {"agent_id": str(agent.id)}}])


def semantic_query(text: str, top_k: int = 8) -> list[dict[str, Any]]:
    settings = get_settings()
    if not settings.pinecone_api_key or Pinecone is None or not settings.openai_api_key:
        return []
    provider = OpenAIProvider()
    vec = provider.embed([text])[0]
    pc = Pinecone(api_key=settings.pinecone_api_key)
    index = pc.Index(INDEX_NAME)  # type: ignore[attr-defined]
    out = index.query(vector=vec, top_k=top_k, include_metadata=True)
    return [
        {"id": m["id"], "score": m.get("score"), "metadata": m.get("metadata", {})}
        for m in getattr(out, "matches", [])
    ]
