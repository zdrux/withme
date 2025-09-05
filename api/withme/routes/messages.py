from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, Query, Header
from sqlalchemy import select

from ..security import get_current_user
from ..db import session_scope
from .. import crud
from ..models import Message


router = APIRouter()


@router.get("/messages")
async def list_messages(
    limit: int = Query(50, le=200),
    before: str | None = Query(None, description="ISO timestamp to paginate backwards"),
    user=Depends(get_current_user),
    x_agent_id: str | None = Header(default=None, alias="X-Agent-ID"),
):
    user_id = uuid.UUID(str(user["id"]))
    async with session_scope() as session:
        db_user = await crud.get_or_create_user(session, user_id=user_id, email=user.get("email", "dev@example.com"))
        try:
            aid = uuid.UUID(x_agent_id) if x_agent_id else None
        except Exception:
            aid = None
        agent = await crud.get_agent_for_user(session, db_user, aid)
        q = (
            select(Message)
            .where(Message.user_id == db_user.id, Message.agent_id == agent.id)
            .order_by(Message.created_at.desc())
        )
        if before:
            from datetime import datetime

            try:
                bt = datetime.fromisoformat(before)
                q = q.where(Message.created_at < bt)
            except Exception:
                pass
        q = q.limit(limit)
        res = await session.execute(q)
        rows = res.scalars().all()
        data = [
            {
                "id": str(m.id),
                "role": m.role,
                "text": m.text,
                "image_url": m.image_url,
                "created_at": m.created_at.isoformat(),
            }
            for m in rows
        ]
        next_before = rows[-1].created_at.isoformat() if rows else None
        return {"items": data, "next_before": next_before}
