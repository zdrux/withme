from fastapi import APIRouter
from pydantic import BaseModel, HttpUrl
import uuid

from ..db import session_scope
from ..models import ImageJob, Agent, Message


router = APIRouter()


class FalWebhook(BaseModel):
    job_id: str
    status: str
    url: HttpUrl | None = None


@router.post("/fal", status_code=204)
async def fal_webhook(payload: FalWebhook):
    # Update image_jobs by job_id, and append an agent message with image_url if succeeded
    try:
        job_id = uuid.UUID(str(payload.job_id))
    except Exception:
        # Ignore malformed IDs silently to avoid leaking
        return
    async with session_scope() as session:
        job = await session.get(ImageJob, job_id)
        if not job:
            return
        status_lower = (payload.status or "").lower()
        if status_lower in {"succeeded", "success", "completed"} and payload.url:
            job.status = "succeeded"
            job.result_url = str(payload.url)
            agent = await session.get(Agent, job.agent_id)
            if agent:
                msg = Message(user_id=agent.user_id, agent_id=agent.id, role="agent", text=None, image_url=str(payload.url))
                session.add(msg)
        elif status_lower in {"failed", "error"}:
            job.status = "failed"
        else:
            job.status = "running"
    return
