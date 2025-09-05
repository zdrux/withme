import uuid
from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel
from sqlalchemy import select

from ..security import get_current_user
from ..db import session_scope
from .. import crud
from ..models import Scenario, Event


router = APIRouter()


class CreateAgentReq(BaseModel):
    name: str
    persona: dict
    romance_allowed: bool = False
    initiation_tendency: float | None = None


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
        return {"id": str(ag.id)}


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
async def list_scenarios(user=Depends(get_current_user)):
    uid = uuid.UUID(str(user["id"]))
    async with session_scope() as session:
        db_user = await crud.get_or_create_user(session, user_id=uid, email=user.get("email", "dev@example.com"))
        agent = await crud.get_or_create_agent(session, db_user)
        res = await session.execute(select(Scenario).where(Scenario.agent_id == agent.id).order_by(Scenario.track))
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
async def list_events(limit: int = 50, user=Depends(get_current_user)):
    uid = uuid.UUID(str(user["id"]))
    async with session_scope() as session:
        db_user = await crud.get_or_create_user(session, user_id=uid, email=user.get("email", "dev@example.com"))
        agent = await crud.get_or_create_agent(session, db_user)
        res = await session.execute(select(Event).where(Event.agent_id == agent.id).order_by(Event.occurred_at.desc()).limit(limit))
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
