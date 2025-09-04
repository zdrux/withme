from fastapi import APIRouter
from pydantic import BaseModel, HttpUrl


router = APIRouter()


class FalWebhook(BaseModel):
    job_id: str
    status: str
    url: HttpUrl | None = None


@router.post("/fal", status_code=204)
async def fal_webhook(payload: FalWebhook):
    # TODO: update image_jobs, append agent message with image_url
    _ = payload
    return

