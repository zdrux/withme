import uuid
from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel
from sqlalchemy import select
import json

from ..security import get_current_user
from ..db import session_scope
from .. import crud
from ..models import Scenario, Event, Agent, ImageJob
from ..providers.openai_client import OpenAIProvider
from ..services.storage import ensure_public_bucket


router = APIRouter()


class CreateAgentReq(BaseModel):
    name: str
    persona: dict
    romance_allowed: bool = False
    initiation_tendency: float | None = None
    appearance_prompt: str | None = None


@router.post("")
async def create_agent(req: CreateAgentReq, user=Depends(get_current_user)):
    uid = uuid.UUID(str(user["id"]))
    async with session_scope() as session:
        db_user = await crud.get_or_create_user(session, user_id=uid, email=user.get("email", "dev@example.com"))
        # naive create a new agent (allow multiple agents per user if needed)
        from ..models import Agent

        ag = Agent(
            user_id=db_user.id,
            name=req.name,
            persona_json=req.persona,
            romance_allowed=req.romance_allowed,
            initiation_tendency=req.initiation_tendency or 0.4,
        )
        session.add(ag)
        await session.flush()
        # Optional base image generation
        if req.appearance_prompt:
            from ..models import ImageJob
            job = ImageJob(agent_id=ag.id, prompt=req.appearance_prompt, status='queued', kind='base')
            session.add(job)
            await session.flush()
            from ..jobs import get_queue
            q = get_queue()
            q.enqueue("worker.tasks.process_image_job", str(job.id))
        return {"id": str(ag.id)}


class GenerateAgentReq(BaseModel):
    name: str | None = None
    archetype: str | None = None
    traits: list[str] | None = None
    likes: list[str] | None = None
    dislikes: list[str] | None = None
    romance_allowed: bool = False
    initiation_tendency: float | None = None
    image_threshold: float | None = None
    appearance_prompt: str | None = None


@router.post("/agent/generate")
async def generate_agent(req: GenerateAgentReq, user=Depends(get_current_user)):
    """Generate an agent profile (persona + offline life + goals) and create it.

    Uses OpenAI if configured; falls back to a templated persona.
    """
    uid = uuid.UUID(str(user["id"]))
    async with session_scope() as session:
        db_user = await crud.get_or_create_user(session, user_id=uid, email=user.get("email", "dev@example.com"))

        persona: dict
        tracks: dict[str, dict]
        summary: str
        traits = req.traits or []
        likes = req.likes or []
        dislikes = req.dislikes or []
        archetype = req.archetype or "busy professional with a soft side"
        name = req.name or "Daniel"

        try:
            from ..config import get_settings

            settings = get_settings()
            if not settings.openai_api_key:
                raise RuntimeError("no_openai")
            provider = OpenAIProvider()
            system = (
                "You are an assistant that outputs ONLY JSON. Generate an AI companion profile.\n"
                "Fields: {\n"
                "  \"summary\": str, \"traits\": [str], \"likes\": [str], \"dislikes\": [str],\n"
                "  \"backstory\": str, \"speaking_style\": str, \"occupation\": str, \"home_city\": str, \"timezone\": str,\n"
                "  \"appearance\": {\"base_image_prompt\": str},\n"
                "  \"offline_life\": {\n"
                "    \"availability\": {\"commute\": \"07-09\", \"work\": \"09-17\", \"evening\": \"18-23\", \"sleep\": \"23-07\"},\n"
                "    \"habits\": [str]\n"
                "  },\n"
                "  \"goals\": {\n"
                "    \"A\": {\"title\": str, \"state\": {}},\n"
                "    \"B\": {\"title\": str, \"state\": {}},\n"
                "    \"C\": {\"title\": str, \"state\": {}},\n"
                "    \"D\": {\"title\": str, \"state\": {}}\n"
                "  },\n"
                "  \"safety\": {\"no_romance\": bool, \"boundaries\": [str]}\n"
                "}\n"
                "Keep PG-13; align with seeds."
            )
            seeds = {
                "name": name,
                "archetype": archetype,
                "traits": traits,
                "likes": likes,
                "dislikes": dislikes,
                "romance_allowed": req.romance_allowed,
            }
            out = provider.chat(system, [{"role": "user", "content": json.dumps(seeds)}])
            # Extract JSON robustly
            start = out.find("{")
            end = out.rfind("}")
            j = json.loads(out[start : end + 1]) if start != -1 and end != -1 else json.loads(out)
            persona = {
                "summary": j.get("summary", ""),
                "traits": j.get("traits", []),
                "likes": j.get("likes", []),
                "dislikes": j.get("dislikes", []),
                "backstory": j.get("backstory", ""),
                "speaking_style": j.get("speaking_style", ""),
                "occupation": j.get("occupation", ""),
                "home_city": j.get("home_city", ""),
                "timezone": j.get("timezone", ""),
                "appearance": j.get("appearance", {}),
                "offline_life": j.get("offline_life", {}),
                "safety": j.get("safety", {}),
            }
            tracks = j.get("goals", {})
            summary = persona.get("summary", "")
        except Exception:
            # Fallback template
            # Fallback template with light randomization
            import random
            cities = [
                ("New York", "America/New_York"),
                ("Los Angeles", "America/Los_Angeles"),
                ("Chicago", "America/Chicago"),
                ("London", "Europe/London"),
                ("Berlin", "Europe/Berlin"),
                ("Sydney", "Australia/Sydney"),
                ("Toronto", "America/Toronto"),
            ]
            city, tz = random.choice(cities)
            occupation = random.choice(["product manager", "designer", "software engineer", "nurse", "teacher", "barista"])
            persona = {
                "summary": f"{name} is a {archetype} who values connection and small rituals.",
                "traits": (traits or ["witty", "grounded", "curious"])[:5],
                "likes": (likes or ["coffee", "long walks", "music"])[:5],
                "dislikes": (dislikes or ["lateness"])[:5],
                "backstory": "Grew up in a small town, moved to the city for work; keeps weekends for friends and self-care.",
                "speaking_style": "Warm, lightly self-deprecating humor, concise during work hours.",
                "occupation": occupation,
                "home_city": city,
                "timezone": tz,
                "appearance": {"base_image_prompt": req.appearance_prompt or "portrait, warm lighting"},
                "offline_life": {
                    "availability": {"commute": "07-09", "work": "09-17", "evening": "18-23", "sleep": "23-07"},
                    "habits": ["Morning coffee", "Evening run 3x/week"],
                },
                "safety": {"no_romance": not req.romance_allowed, "boundaries": ["PG-13 only"]},
            }
            tracks = {
                "A": {"title": "Grow into a leadership role", "state": {}},
                "B": {"title": "Build a meaningful connection", "state": {}},
                "C": {"title": "Support a friend through changes", "state": {}},
                "D": {"title": "Buy a reliable used car", "state": {}},
            }
            summary = persona["summary"]

        tzname = persona.get("timezone") or "UTC"
        ag = Agent(
            user_id=db_user.id,
            name=name,
            persona_json=persona,
            romance_allowed=req.romance_allowed,
            initiation_tendency=req.initiation_tendency or 0.4,
            image_threshold=req.image_threshold or 0.6,
            timezone=tzname,
        )
        session.add(ag)
        await session.flush()
        # Optional base image generation
        base_prompt = req.appearance_prompt or persona.get("appearance", {}).get("base_image_prompt")
        if base_prompt:
            job = ImageJob(agent_id=ag.id, prompt=str(base_prompt), status='queued', kind='base')
            session.add(job)
            await session.flush()
            from ..jobs import get_queue
            q = get_queue()
            q.enqueue("worker.tasks.process_image_job", str(job.id))
        # Seed scenarios from tracks
        for t in ("A", "B", "C", "D"):
            if t in tracks:
                s = Scenario(
                    agent_id=ag.id,
                    track=t,
                    title=str(tracks[t].get("title", f"Track {t}")),
                    state_json=tracks[t].get("state", {}),
                    progress=0.0,
                )
                session.add(s)

        return {"id": str(ag.id), "name": ag.name, "persona": ag.persona_json}


@router.get("/agents")
async def list_agents(user=Depends(get_current_user)):
    uid = uuid.UUID(str(user["id"]))
    async with session_scope() as session:
        db_user = await crud.get_or_create_user(session, user_id=uid, email=user.get("email", "dev@example.com"))
        res = await session.execute(select(Agent).where(Agent.user_id == db_user.id).order_by(Agent.created_at.desc()))
        items = []
        for a in res.scalars().all():
            items.append({
                "id": str(a.id),
                "name": a.name,
                "romance_allowed": a.romance_allowed,
                "initiation_tendency": a.initiation_tendency,
                "image_threshold": a.image_threshold,
                "mood": a.mood,
                "affinity": a.affinity,
                "created_at": a.created_at.isoformat(),
            })
        return {"items": items}


class UpdateAgentReq(BaseModel):
    name: str | None = None
    persona: dict | None = None
    romance_allowed: bool | None = None
    initiation_tendency: float | None = None
    image_threshold: float | None = None
    mood: float | None = None
    affinity: float | None = None
    timezone: str | None = None


@router.patch("/agents/{agent_id}")
async def update_agent(agent_id: str, req: UpdateAgentReq, user=Depends(get_current_user)):
    _ = user
    async with session_scope() as session:
        ag = await session.get(Agent, uuid.UUID(agent_id))
        if not ag:
            return {"ok": False, "error": "not_found"}
        if req.name is not None:
            ag.name = req.name
        if req.persona is not None:
            ag.persona_json = req.persona
        if req.romance_allowed is not None:
            ag.romance_allowed = bool(req.romance_allowed)
        if req.initiation_tendency is not None:
            ag.initiation_tendency = float(req.initiation_tendency)
        if req.image_threshold is not None:
            ag.image_threshold = float(req.image_threshold)
        if req.mood is not None:
            ag.mood = float(req.mood)
        if req.affinity is not None:
            ag.affinity = max(0.0, min(1.0, float(req.affinity)))
        if req.timezone is not None:
            ag.timezone = req.timezone
        return {"ok": True}


@router.delete("/agents/{agent_id}", status_code=204)
async def delete_agent(agent_id: str, user=Depends(get_current_user)):
    uid = uuid.UUID(str(user["id"]))
    async with session_scope() as session:
        # Ensure agent exists and belongs to current user
        ag = await session.get(Agent, uuid.UUID(agent_id))
        if not ag:
            return  # 204 for idempotency; avoid leaking info
        # Confirm ownership
        from ..models import User

        owner = await session.get(User, ag.user_id)
        if not owner or owner.id != uid:
            return  # 204 to avoid user enumeration
        await session.delete(ag)
        # cascades handle messages/events/scenarios/etc.
        return


class EnsureBucketReq(BaseModel):
    bucket: str = "agent-avatars"


@router.post("/storage/ensure_bucket")
async def storage_ensure_bucket(req: EnsureBucketReq, user=Depends(get_current_user)):
    _ = user
    ok = ensure_public_bucket(req.bucket)
    return {"ok": ok, "bucket": req.bucket}


@router.get("/agents/{agent_id}")
async def get_agent_detail(agent_id: str, user=Depends(get_current_user)):
    _ = user
    async with session_scope() as session:
        ag = await session.get(Agent, uuid.UUID(agent_id))
        if not ag:
            return {"ok": False, "error": "not_found"}
        # Best-effort backfill: if base_image_url missing, use last succeeded base job's result_url
        if not ag.base_image_url:
            from sqlalchemy import select as _select
            from ..models import ImageJob
            res = await session.execute(
                _select(ImageJob).where(ImageJob.agent_id == ag.id, ImageJob.kind == 'base', ImageJob.status == 'succeeded').order_by(ImageJob.created_at.desc()).limit(1)
            )
            job = res.scalars().first()
            if job and job.result_url:
                ag.base_image_url = job.result_url
        return {
            "id": str(ag.id),
            "name": ag.name,
            "persona": ag.persona_json,
            "romance_allowed": ag.romance_allowed,
            "initiation_tendency": ag.initiation_tendency,
            "image_threshold": ag.image_threshold,
            "mood": ag.mood,
            "affinity": ag.affinity,
            "base_image_url": ag.base_image_url,
            "created_at": ag.created_at.isoformat(),
        }


class SeedScenariosReq(BaseModel):
    agent_id: str
    seeds: dict


@router.post("/scenarios/seed")
async def seed_scenarios(req: SeedScenariosReq, user=Depends(get_current_user)):
    _ = user
    async with session_scope() as session:
        for track, payload in req.seeds.items():
            s = Scenario(
                agent_id=uuid.UUID(req.agent_id),
                track=str(track),
                title=payload.get("title", f"Track {track}"),
                state_json=payload.get("state", {}),
                progress=float(payload.get("progress", 0.0)),
            )
            session.add(s)
        return {"ok": True}


@router.get("/scenarios")
async def list_scenarios(agent_id: str | None = Query(None), user=Depends(get_current_user)):
    uid = uuid.UUID(str(user["id"]))
    async with session_scope() as session:
        db_user = await crud.get_or_create_user(session, user_id=uid, email=user.get("email", "dev@example.com"))
        target_agent_id: uuid.UUID
        if agent_id:
            try:
                aid = uuid.UUID(agent_id)
            except Exception:
                return []
            ag = await session.get(Agent, aid)
            if not ag or ag.user_id != db_user.id:
                return []
            target_agent_id = ag.id
        else:
            ag = await crud.get_or_create_agent(session, db_user)
            target_agent_id = ag.id
        res = await session.execute(select(Scenario).where(Scenario.agent_id == target_agent_id).order_by(Scenario.track))
        return [
            {"id": str(s.id), "track": s.track, "title": s.title, "progress": s.progress, "state": s.state_json}
            for s in res.scalars().all()
        ]


class UpdateScenarioReq(BaseModel):
    title: str | None = None
    progress: float | None = None
    state: dict | None = None


@router.patch("/scenarios/{scenario_id}")
async def update_scenario(scenario_id: str = Path(...), req: UpdateScenarioReq | None = None, user=Depends(get_current_user)):
    _ = user
    async with session_scope() as session:
        s = await session.get(Scenario, uuid.UUID(scenario_id))
        if not s:
            return {"ok": False, "error": "not_found"}
        if req:
            if req.title is not None:
                s.title = req.title
            if req.progress is not None:
                s.progress = req.progress
            if req.state is not None:
                s.state_json = req.state
        return {"ok": True}


@router.get("/events")
async def list_events(limit: int = 50, agent_id: str | None = Query(None), user=Depends(get_current_user)):
    uid = uuid.UUID(str(user["id"]))
    async with session_scope() as session:
        db_user = await crud.get_or_create_user(session, user_id=uid, email=user.get("email", "dev@example.com"))
        target_agent_id: uuid.UUID
        if agent_id:
            try:
                aid = uuid.UUID(agent_id)
            except Exception:
                return []
            ag = await session.get(Agent, aid)
            if not ag or ag.user_id != db_user.id:
                return []
            target_agent_id = ag.id
        else:
            ag = await crud.get_or_create_agent(session, db_user)
            target_agent_id = ag.id
        res = await session.execute(
            select(Event).where(Event.agent_id == target_agent_id).order_by(Event.occurred_at.desc()).limit(limit)
        )
        return [
            {
                "id": str(e.id),
                "type": e.type,
                "payload": e.payload_json,
                "mood_delta": e.mood_delta,
                "occurred_at": e.occurred_at.isoformat(),
            }
            for e in res.scalars().all()
        ]
