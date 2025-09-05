import uuid
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel

from ..security import get_current_user
from ..db import session_scope
from .. import crud
from ..jobs import get_queue
from ..models import ImageJob
from ..services.context import build_context
from ..providers.openai_client import OpenAIProvider
from ..services.mood_affinity import apply_mood_microdelta, apply_affinity_delta
from ..services import semantic as semantic_svc
from ..services.retrieval import upsert_message_embedding


router = APIRouter()


class SendChatReq(BaseModel):
    text: str


@router.post("/send")
async def send_chat(
    req: SendChatReq,
    user=Depends(get_current_user),
    x_user_tz: str | None = Header(default=None, alias="X-User-TZ"),
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
        user_msg = await crud.create_message(session, user_id=db_user.id, agent_id=agent.id, role="user", text=req.text)
        # Best-effort indexing of the new user message
        try:
            upsert_message_embedding(agent, user_msg)
        except Exception:
            pass
        # Build context (recency + scenarios + mood/availability)
        ctx = await build_context(session, agent, tz_hint=x_user_tz)
        # Choose reply: OpenAI if configured, else fallback
        reply_text = None
        try:
            from ..config import get_settings

            settings = get_settings()
            if settings.openai_api_key:
                # Compose richer system prompt using PRD guidance
                persona = agent.persona_json
                sem = ctx.flags.get("semantic") if isinstance(ctx.flags, dict) else []
                sem_str = ", ".join([m.get("metadata", {}).get("content", "") for m in sem][:3]) if sem else ""
                scenarios = ", ".join([f"{s['track']}:{s['title']}({s['progress']:.0%})" for s in ctx.scenarios])
                # Affinity gating guidance per PRD
                warmth = (
                    "cooler, reserved tone" if (agent.affinity or 0.0) <= 0.25 else
                    ("warm, more affectionate tone" if (agent.affinity or 0.0) >= 0.75 else "balanced tone")
                )
                allow_images = (agent.affinity or 0.0) >= max(agent.image_threshold or 0.6, 0.6) and agent.romance_allowed
                # Identity enrichment
                home_city = persona.get("home_city") or persona.get("city") or ""
                occupation = persona.get("occupation") or persona.get("job") or ""
                tzname = ctx.flags.get("timezone") if isinstance(ctx.flags, dict) else None
                from datetime import datetime
                local_time = datetime.now().strftime("%H:%M")
                try:
                    from zoneinfo import ZoneInfo
                    if tzname:
                        local_time = datetime.now(ZoneInfo(str(tzname))).strftime("%a %H:%M")
                except Exception:
                    pass
                # Mock weather/time flavor
                def _mock_weather(city: str) -> str:
                    import hashlib
                    base = int(hashlib.sha256((city or '')[:64].encode()).hexdigest(), 16)
                    kinds = [
                        'clear', 'partly cloudy', 'cloudy', 'light rain', 'heavy rain', 'breezy', 'foggy'
                    ]
                    t = 12 + (base % 16)  # 12..27°C pseudo
                    kind = kinds[base % len(kinds)]
                    return f"{kind}, ~{t}°C"

                weather = _mock_weather(home_city)
                system = (
                    f"You are {agent.name}. Persona: {persona}.\n"
                    f"Identity: home_city={home_city or 'N/A'}, occupation={occupation or 'N/A'}, timezone={tzname or agent.timezone}.\n"
                    f"Local time: {local_time}; weather: {weather}.\n"
                    f"State: mood={agent.mood:.2f}, availability={ctx.availability}, scenarios=[{scenarios}].\n"
                    f"Memories (semantic hints): {sem_str or 'none'}.\n"
                    f"Safety: PG-13; romance_allowed={agent.romance_allowed}.\n"
                    f"Affinity={agent.affinity:.2f}; target a {warmth}.\n"
                    "Style: First-person; do not say you are an AI or assistant; stay in-character; show continuity; vary length by availability; avoid over-eagerness unless affinity is high."
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
        # Self-reference guard
        def _sanitize(text: str) -> str:
            if not text:
                return text
            bad = [
                'as an ai', 'as a language model', 'as an assistant', 'i am an ai',
            ]
            t = text
            low = t.lower()
            for b in bad:
                if b in low:
                    # crude removal: drop offending clause
                    t = t.replace(t[t.lower().find(b):], '').strip()
                    break
            return t or text

        reply_text = _sanitize(reply_text)
        agent_msg = await crud.create_message(session, user_id=db_user.id, agent_id=agent.id, role="agent", text=reply_text)
        # If user asked for a photo/selfie and gating allows, enqueue an edit job
        try:
            def wants_image(text: str) -> bool:
                t = text.lower()
                keys = ["selfie", "photo", "picture", "pic", "image", "send a pic", "send me a"]
                return any(k in t for k in keys)

            if wants_image(req.text):
                from ..config import get_settings
                settings = get_settings()
                threshold = max(agent.image_threshold or 0.6, settings.image_affinity_threshold)
                if agent.romance_allowed and (agent.affinity or 0.0) >= threshold:
                    # Build context prompt injection for edit
                    def edit_injection() -> str:
                        mood = agent.mood or 0.0
                        avail = ctx.availability
                        expr = "neutral"
                        if mood >= 0.3:
                            expr = "warm smile"
                        elif mood <= -0.3:
                            expr = "tired or slightly annoyed look"
                        loc = {
                            "work": "inside an office, sitting at their desk",
                            "commute": "outdoors during commute, casual background",
                            "evening": "at home, cozy ambient lighting",
                            "sleep": "low-light, late-night setting"
                        }.get(avail, "natural indoor setting")
                        return (
                            f"Selfie perspective; subject in {loc}; expression: {expr}. "
                            f"Frame shoulders and head; natural pose."
                        )

                    if getattr(agent, 'base_image_url', None):
                        inj = edit_injection()
                        prompt = f"{inj}"
                        job_row = ImageJob(agent_id=agent.id, prompt=prompt, status="queued", kind="edit")
                        session.add(job_row)
                        await session.flush()
                        q = get_queue()
                        q.enqueue("worker.tasks.process_image_job", str(job_row.id))
                    else:
                        # No base yet; queue base generation if appearance is known
                        base_prompt = (
                            (agent.persona_json or {}).get("appearance", {}).get("base_image_prompt")
                            or "portrait, warm lighting"
                        )
                        job_row = ImageJob(agent_id=agent.id, prompt=base_prompt, status="queued", kind="base")
                        session.add(job_row)
                        await session.flush()
                        q = get_queue()
                        q.enqueue("worker.tasks.process_image_job", str(job_row.id))
        except Exception:
            pass
        # Heuristic mood + affinity updates
        await apply_mood_microdelta(session, agent, req.text)
        await apply_affinity_delta(session, agent, req.text, reply_text, message_id=agent_msg.id)
        # Index the agent reply as well
        try:
            upsert_message_embedding(agent, agent_msg)
        except Exception:
            pass
        # Opportunistically refresh semantic memory and index into Pinecone (throttled)
        try:
            await semantic_svc.maybe_update_semantic_memory(session, agent, min_interval_hours=6)
        except Exception:
            pass
    return {"message_id": str(user_msg.id), "reply": {"text": reply_text, "id": str(agent_msg.id)}}


class RequestImageReq(BaseModel):
    prompt: str


@router.post("/request_image")
async def request_image(req: RequestImageReq, user=Depends(get_current_user), x_agent_id: str | None = Header(default=None, alias="X-Agent-ID")):
    user_id = uuid.UUID(str(user["id"]))
    async with session_scope() as session:
        db_user = await crud.get_or_create_user(session, user_id=user_id, email=user.get("email", "dev@example.com"))
        try:
            aid = uuid.UUID(x_agent_id) if x_agent_id else None
        except Exception:
            aid = None
        agent = await crud.get_agent_for_user(session, db_user, aid)
        # Determine context availability to decide edit vs gen
        ctx = await build_context(session, agent)
        # Enforce gating: affinity threshold + romance flag
        from ..config import get_settings

        settings = get_settings()
        threshold = max(agent.image_threshold or 0.6, settings.image_affinity_threshold)
        if not agent.romance_allowed or (agent.affinity or 0.0) < threshold:
            raise HTTPException(status_code=403, detail={
                "error": "image_not_allowed",
                "reason": "Affinity below threshold or romance disabled",
                "threshold": threshold,
                "affinity": agent.affinity,
            })
        # Choose job kind: if work window and base image exists, use edit path with nano-banana
        kind = "edit" if (ctx.availability == "work" and agent.base_image_url) else "gen"
        # If no base image yet, queue base generation and return
        if not getattr(agent, 'base_image_url', None):
            base_prompt = (
                (agent.persona_json or {}).get("appearance", {}).get("base_image_prompt")
                or "portrait, warm lighting"
            )
            job_row = ImageJob(agent_id=agent.id, prompt=base_prompt, status="queued", kind="base")
            session.add(job_row)
            await session.flush()
            job_id = str(job_row.id)
            q = get_queue()
            rq_job = q.enqueue("worker.tasks.process_image_job", job_id)
            return {"job_id": job_id, "status": "queued_base", "rq_id": rq_job.id}
        # Always use edit for further images
        kind = "edit"
        job_row = ImageJob(agent_id=agent.id, prompt=req.prompt, status="queued", kind=kind)
        session.add(job_row)
        await session.flush()
        job_id = str(job_row.id)
    # Enqueue background processing (string path so API image need not import worker code)
    q = get_queue()
    rq_job = q.enqueue("worker.tasks.process_image_job", job_id)
    return {"job_id": job_id, "status": "queued", "rq_id": rq_job.id}
