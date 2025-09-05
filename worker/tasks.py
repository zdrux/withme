from __future__ import annotations

import time
from typing import Any
import asyncio
import time
import os
import requests

from api.withme.db import session_scope
from api.withme.models import ImageJob, Message, Agent


def process_image_job(image_job_id: str) -> dict[str, Any]:
    """
    Submit prompt to Fal.AI flux-pro v1.1-ultra queue and poll for result.
    Falls back to a placeholder URL if API key/network is unavailable.
    """
    url = None

    try:
        from api.withme.config import get_settings

        settings = get_settings()
        api_key = settings.fal_api_key
        if api_key:
            # Load job for prompt
            prompt = None
            agent_id = None
            # quick fetch of job row
            def _fetch():
                return prompt, agent_id

            # We can't reuse async session here; we'll pull in update coroutine anyway.
            # Let's do small async block to fetch prompt/agent_id
            async def _get():
                nonlocal prompt, agent_id
                async with session_scope() as session:
                    job = await session.get(ImageJob, image_job_id)
                    if job:
                        prompt = job.prompt
                        agent_id = job.agent_id

            asyncio.run(_get())

            if prompt:
                headers = {"Authorization": f"Key {api_key}", "Content-Type": "application/json"}
                submit = requests.post(
                    "https://queue.fal.run/fal-ai/flux-pro/v1.1-ultra",
                    json={"prompt": prompt},
                    headers=headers,
                    timeout=10,
                )
                submit.raise_for_status()
                data = submit.json()
                req_id = data.get("request_id") or data.get("id")
                if req_id:
                    # poll
                    for _ in range(30):
                        time.sleep(2)
                        r = requests.get(
                            f"https://queue.fal.run/requests/{req_id}", headers=headers, timeout=10
                        )
                        if r.status_code >= 500:
                            continue
                        j = r.json()
                        status = (j.get("status") or "").lower()
                        if status in {"succeeded", "completed", "success"}:
                            # guess result path
                            result = j.get("response") or j.get("result") or j
                            # attempt to find an URL
                            for key in ("image", "url", "image_url", "output_url"):
                                if isinstance(result, dict) and key in result:
                                    url = result[key]
                                    break
                            break
                        if status in {"failed", "error"}:
                            break
    except Exception:
        # leave url as None to use placeholder
        url = None

    if url is None:
        url = "https://picsum.photos/seed/withme/512/768"

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
