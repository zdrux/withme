import uuid
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..security import get_current_user
from ..db import session_scope
from .. import crud
from ..jobs import get_queue
from ..models import ImageJob


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
        # Placeholder inference
        reply_text = "Just finished a tough meeting, glad to hear from you."
        agent_msg = await crud.create_message(session, user_id=db_user.id, agent_id=agent.id, role="agent", text=reply_text)
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
