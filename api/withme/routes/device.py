import uuid
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..security import get_current_user
from ..db import session_scope
from .. import crud


router = APIRouter()


class RegisterDeviceReq(BaseModel):
    platform: str
    token: str


@router.post("/fcm", status_code=204)
async def register_device(req: RegisterDeviceReq, user=Depends(get_current_user)):
    user_id = uuid.UUID(str(user["id"]))
    async with session_scope() as session:
        db_user = await crud.get_or_create_user(session, user_id=user_id, email=user.get("email", "dev@example.com"))
        await crud.upsert_device(session, db_user, platform=req.platform, token=req.token)
    return
