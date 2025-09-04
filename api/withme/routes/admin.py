from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..security import get_current_user


router = APIRouter()


class CreateAgentReq(BaseModel):
    name: str
    persona: dict
    romance_allowed: bool = False
    initiation_tendency: float | None = None


@router.post("")
async def create_agent(req: CreateAgentReq, user=Depends(get_current_user)):
    # TODO: persist agent and return id
    _ = (req, user)
    return {"id": "00000000-0000-0000-0000-0000000000AA"}


class SeedScenariosReq(BaseModel):
    agent_id: str
    seeds: dict


@router.post("/scenarios/seed")
async def seed_scenarios(req: SeedScenariosReq, user=Depends(get_current_user)):
    # TODO: invoke LLM to seed scenarios A–D and persist
    _ = (req, user)
    return {"ok": True}
