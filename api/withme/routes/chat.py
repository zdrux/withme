import uuid
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..security import get_current_user
from ..db import session_scope
from .. import crud
from ..jobs import get_queue
from ..models import ImageJob
from ..services.context import build_context
from ..providers.openai_client import OpenAIProvider
from ..services.mood_affinity import apply_mood_microdelta, apply_affinity_delta


router = APIRouter()


class SendChatReq(BaseModel):
    text: str


@router.post("/send")
async def send_chat(req: SendChatReq, user=Depends(get_current_user)):
    user_id = uuid.UUID(str(user["id"]))
    async with session_scope() as session:
        db_user = await crud.get_or_create_user(session, user_id=user_id, email=user.get("email", "dev@example.com"))
        agent = await crud.get_or_create_agent(session, db_user)
        user_msg = await crud.create_message(session, user_id=db_user.id, agent_id=agent.id, role="user", text=req.text)
        # Build context (recency + scenarios + mood/availability)
        ctx = await build_context(session, agent)
        # Choose reply: OpenAI if configured, else fallback
        reply_text = None
        try:
            from ..config import get_settings

            settings = get_settings()
            if settings.openai_api_key:
                system = (
                    f"You are {agent.name}, an AI companion.\n"
                    f"Persona: {agent.persona_json}. Safety: PG-13; no explicit content.\n"
                    f"State: mood={agent.mood}, availability={ctx.availability}, scenarios={ctx.scenarios}.\n"
                    "Style: Vary length by availability; stay in-character; show continuity."
                )
                user_msgs = [{"role": "user", "content": req.text}]
                provider = OpenAIProvider()
                reply_text = provider.chat(system, user_msgs)
        except Exception:
            reply_text = None

        if not reply_text:
            if ctx.availability == "work":
                reply_text = "At work, swamped! Ping me later?"
            elif ctx.availability == "evening":
                reply_text = "Just finished a tough meeting, glad to hear from you."
            else:
                reply_text = "Catching my breath—what’s on your mind?"
        agent_msg = await crud.create_message(session, user_id=db_user.id, agent_id=agent.id, role="agent", text=reply_text)
        # Heuristic mood + affinity updates
        await apply_mood_microdelta(session, agent, req.text)
        await apply_affinity_delta(session, agent, req.text, reply_text)
    return {"message_id": str(user_msg.id), "reply": {"text": reply_text, "id": str(agent_msg.id)}}


class RequestImageReq(BaseModel):
    prompt: str


@router.post("/request_image")
async def request_image(req: RequestImageReq, user=Depends(get_current_user)):
    user_id = uuid.UUID(str(user["id"]))
    async with session_scope() as session:
        db_user = await crud.get_or_create_user(session, user_id=user_id, email=user.get("email", "dev@example.com"))
        agent = await crud.get_or_create_agent(session, db_user)
        # Create queued job record
        job_row = ImageJob(agent_id=agent.id, prompt=req.prompt, status="queued")
        session.add(job_row)
        await session.flush()
        job_id = str(job_row.id)
    # Enqueue background processing (string path so API image need not import worker code)
    q = get_queue()
    rq_job = q.enqueue("worker.tasks.process_image_job", job_id)
    return {"job_id": job_id, "status": "queued", "rq_id": rq_job.id}
