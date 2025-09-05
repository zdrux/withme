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
EMBED_DIM = 1536


def _ensure_index(pc) -> Any:
    # Ensure index exists with correct dim/metric
    try:
        names = [i.name for i in pc.list_indexes()]  # type: ignore[attr-defined]
    except Exception:
        names = []
    if INDEX_NAME not in names:
        pc.create_index(name=INDEX_NAME, dimension=EMBED_DIM, metric="cosine")  # type: ignore[attr-defined]
    return pc.Index(INDEX_NAME)  # type: ignore[attr-defined]


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
    index = _ensure_index(pc)
    index.upsert(vectors=[{
        "id": f"semantic:{agent.id}:{mem.id}",
        "values": vec,
        "metadata": {
            "type": "semantic",
            "agent_id": str(agent.id),
            "content": mem.content[:500],
        },
    }])


def semantic_query(text: str, top_k: int = 8) -> list[dict[str, Any]]:
    settings = get_settings()
    if not settings.pinecone_api_key or Pinecone is None or not settings.openai_api_key:
        return []
    provider = OpenAIProvider()
    vec = provider.embed([text])[0]
    pc = Pinecone(api_key=settings.pinecone_api_key)
    index = _ensure_index(pc)
    out = index.query(vector=vec, top_k=top_k, include_metadata=True)
    return [
        {"id": m["id"], "score": m.get("score"), "metadata": m.get("metadata", {})}
        for m in getattr(out, "matches", [])
    ]


def upsert_message_embedding(agent: Agent, message: Any) -> None:
    """Best-effort embed a single Message row and upsert into Pinecone.

    No-op if dependencies or keys are missing, or text is empty.
    """
    settings = get_settings()
    if not settings.pinecone_api_key or Pinecone is None or not settings.openai_api_key:
        return
    text = getattr(message, "text", None)
    if not text:
        return
    provider = OpenAIProvider()
    vec = provider.embed([text])[0]
    pc = Pinecone(api_key=settings.pinecone_api_key)
    index = _ensure_index(pc)
    meta = {
        "type": "message",
        "agent_id": str(agent.id),
        "user_id": str(getattr(message, "user_id", "")),
        "message_id": str(getattr(message, "id", "")),
        "role": getattr(message, "role", ""),
        "content": text[:500],
    }
    index.upsert(vectors=[{"id": f"message:{message.id}", "values": vec, "metadata": meta}])
