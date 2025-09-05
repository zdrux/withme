from fastapi import APIRouter, Depends, Header

from ..security import get_current_user
from ..db import session_scope
from .. import crud
from . import state as _self  # for type hints without circular imports
from ..services.context import _availability


router = APIRouter()


@router.get("/state")
async def get_state(
    user=Depends(get_current_user),
    x_user_tz: str | None = Header(default=None, alias="X-User-TZ"),
    x_agent_id: str | None = Header(default=None, alias="X-Agent-ID"),
):
    # Lightweight snapshot per PRD: agent_id, availability, mood, romance_allowed
    import uuid
    from datetime import datetime, timezone

    user_id = uuid.UUID(str(user["id"]))
    try:
        async with session_scope() as session:
            db_user = await crud.get_or_create_user(session, user_id=user_id, email=user.get("email", "dev@example.com"))
            try:
                aid = uuid.UUID(x_agent_id) if x_agent_id else None
            except Exception:
                aid = None
            agent = await crud.get_agent_for_user(session, db_user, aid)
            # Prefer header timezone; otherwise use agent.timezone
            from zoneinfo import ZoneInfo
            tzname = x_user_tz or getattr(agent, "timezone", None) or "UTC"
            try:
                now = datetime.now(ZoneInfo(tzname))
            except Exception:
                now = datetime.utcnow()
                tzname = "UTC"
            avail = _availability(now)
            return {
                "agent_id": str(agent.id),
                "availability": avail,
                "mood": agent.mood,
                "romance_allowed": agent.romance_allowed,
                "timezone": tzname,
            }
    except Exception:
        # DB might be unavailable in early dev/test; return a safe stub
        return {
            "agent_id": "00000000-0000-0000-0000-000000000001",
            "availability": _availability(datetime.utcnow()),
            "mood": 0.0,
            "romance_allowed": True,
            "timezone": "UTC",
        }
