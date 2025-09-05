import uuid
from fastapi import APIRouter, Depends, Header

from ..security import get_current_user
from ..db import session_scope
from .. import crud


router = APIRouter()


@router.get("")
async def get_agent(user=Depends(get_current_user), x_agent_id: str | None = Header(default=None, alias="X-Agent-ID")):
    user_id = uuid.UUID(str(user["id"]))
    async with session_scope() as session:
        db_user = await crud.get_or_create_user(session, user_id=user_id, email=user.get("email", "dev@example.com"))
        try:
            aid = uuid.UUID(x_agent_id) if x_agent_id else None
        except Exception:
            aid = None
        agent = await crud.get_agent_for_user(session, db_user, aid)
        return {
            "id": str(agent.id),
            "name": agent.name,
            "persona": agent.persona_json,
            "romance_allowed": agent.romance_allowed,
            "timezone": agent.timezone,
        }
