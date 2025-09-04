from __future__ import annotations

import time
from typing import Any
import asyncio

from api.withme.db import session_scope
from api.withme.models import ImageJob, Message, Agent


def process_image_job(image_job_id: str) -> dict[str, Any]:
    # Placeholder image generation; on completion, update DB and create message
    time.sleep(0.1)
    url = "https://cdn.example.com/fake.jpg"

    async def _update():
        async with session_scope() as session:
            job = await session.get(ImageJob, image_job_id)
            if not job:
                return
            job.status = "succeeded"
            job.result_url = url
            agent = await session.get(Agent, job.agent_id)
            if agent:
                msg = Message(user_id=agent.user_id, agent_id=agent.id, role="agent", text=None, image_url=url)
                session.add(msg)

    asyncio.run(_update())
    return {"status": "succeeded", "url": url, "image_job_id": image_job_id}


def run_daily_event(agent_id: str, seed: int | None = None) -> dict[str, Any]:
    # Placeholder RNG and mood delta
    time.sleep(0.05)
    return {"agent_id": agent_id, "mood_delta": 0.1, "title": "A pleasant walk"}


def run_semantic_refresh(agent_id: str) -> dict[str, Any]:
    time.sleep(0.05)
    return {"agent_id": agent_id, "summary": ["Likes coffee", "Busy weekday schedule"]}
