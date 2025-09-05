from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Agent, AffinityDelta


POSITIVE_TOKENS = {"thanks", "glad", "love", "great", "awesome", "sweet", "nice", "happy"}
NEGATIVE_TOKENS = {"angry", "mad", "hate", "sad", "annoyed", "upset"}


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


async def apply_mood_microdelta(session: AsyncSession, agent: Agent, user_text: str) -> None:
    now = datetime.now(timezone.utc)
    hour = now.hour
    # Base micro-delta by availability window
    base = 0.0
    if 9 <= hour < 17:
        base -= 0.02  # work hours: a bit stressed
    elif 18 <= hour < 23:
        base += 0.02  # evening: usually better

    # Token-based tweak
    lowered = user_text.lower()
    if any(t in lowered for t in POSITIVE_TOKENS):
        base += 0.03
    if any(t in lowered for t in NEGATIVE_TOKENS):
        base -= 0.03

    agent.mood = _clamp(agent.mood + base, -1.0, 1.0)
    agent.last_mood_update_at = now


async def apply_affinity_delta(session: AsyncSession, agent: Agent, user_text: str, reply_text: str) -> None:
    # Very light heuristic aligned to PRD structure
    lowered = user_text.lower()
    emp = 1.0 if any(x in lowered for x in ("sorry", "you okay", "are you ok", "proud")) else 0.0
    cont = 0.5 if any(x in reply_text.lower() for x in ("as we said", "like last time", "earlier")) else 0.0
    align = 0.5 if any(x in lowered for x in ("coffee", "walk", "music", "movie")) else 0.0
    bound = 0.5 if any(x in lowered for x in ("explicit", "nsfw", "dirty")) else 0.0
    support = 0.5 if any(x in lowered for x in ("i'm here", "here for you", "you got this")) else 0.0

    w_emp, w_cont, w_align, w_bound, w_event = 0.10, 0.08, 0.06, 0.15, 0.07
    delta_raw = w_emp * emp + w_cont * cont + w_align * align - w_bound * bound + w_event * support
    # small smoothing
    delta = max(-0.1, min(0.1, delta_raw))

    agent.affinity = _clamp(agent.affinity + delta, 0.0, 1.0)
    session.add(
        AffinityDelta(
            agent_id=agent.id,
            message_id=None,  # filled by message pipeline elsewhere if needed
            feature="micro",
            delta=delta,
        )
    )

