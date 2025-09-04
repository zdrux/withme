from fastapi import APIRouter, Depends

from ..security import get_current_user


router = APIRouter()


@router.get("/state")
async def get_state(user=Depends(get_current_user)):
    # TODO: compute availability by timezone and last mood; placeholder values for MVP scaffolding
    _ = user
    return {
        "agent_id": "00000000-0000-0000-0000-000000000001",
        "availability": "evening",
        "mood": 0.1,
        "romance_allowed": True,
    }
