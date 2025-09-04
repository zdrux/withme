from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from ..security import get_current_user
from ..db import session_scope
from .. import crud
from ..models import Message


router = APIRouter()


@router.get("/messages")
async def list_messages(limit: int = Query(50, le=200), user=Depends(get_current_user)):
    user_id = uuid.UUID(str(user["id"]))
    async with session_scope() as session:
        db_user = await crud.get_or_create_user(session, user_id=user_id, email=user.get("email", "dev@example.com"))
        agent = await crud.get_or_create_agent(session, db_user)
        res = await session.execute(
            select(Message)
            .where(Message.user_id == db_user.id, Message.agent_id == agent.id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        rows = res.scalars().all()
        return [
            {
                "id": str(m.id),
                "role": m.role,
                "text": m.text,
                "image_url": m.image_url,
                "created_at": m.created_at.isoformat(),
            }
            for m in rows
        ]

