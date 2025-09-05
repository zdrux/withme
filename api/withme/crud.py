from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User, UserDevice, Agent, Message


async def get_or_create_user(session: AsyncSession, user_id: uuid.UUID, email: str) -> User:
    user = await session.get(User, user_id)
    if user:
        return user
    user = User(id=user_id, email=email, created_at=datetime.utcnow())
    session.add(user)
    await session.flush()
    return user


async def get_or_create_agent(session: AsyncSession, user: User) -> Agent:
    res = await session.execute(select(Agent).where(Agent.user_id == user.id))
    agent = res.scalars().first()
    if agent:
        return agent
    agent = Agent(
        user_id=user.id,
        name="Daniel",
        persona_json={"summary": "Witty, busy professional with warm evenings."},
        romance_allowed=True,
        timezone="UTC",
    )
    session.add(agent)
    await session.flush()
    return agent


async def get_agent_for_user(session: AsyncSession, user: User, agent_id: uuid.UUID | None) -> Agent:
    if agent_id:
        res = await session.execute(select(Agent).where(Agent.id == agent_id, Agent.user_id == user.id))
        found = res.scalars().first()
        if found:
            return found
    return await get_or_create_agent(session, user)


async def upsert_device(session: AsyncSession, user: User, platform: str, token: str) -> UserDevice:
    res = await session.execute(
        select(UserDevice).where(UserDevice.user_id == user.id, UserDevice.fcm_token == token)
    )
    device = res.scalars().first()
    if device:
        device.platform = platform
        device.last_seen_at = datetime.utcnow()
    else:
        device = UserDevice(user_id=user.id, platform=platform, fcm_token=token, last_seen_at=datetime.utcnow())
        session.add(device)
    await session.flush()
    return device


async def create_message(session: AsyncSession, user_id: uuid.UUID, agent_id: uuid.UUID, role: str, text: Optional[str] = None, image_url: Optional[str] = None) -> Message:
    msg = Message(user_id=user_id, agent_id=agent_id, role=role, text=text, image_url=image_url)
    session.add(msg)
    await session.flush()
    return msg
