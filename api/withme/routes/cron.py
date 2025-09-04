from fastapi import APIRouter, Header, HTTPException


router = APIRouter()


def _authorized(internal_token: str | None, header_token: str | None) -> bool:
    return bool(internal_token) and header_token == f"Bearer {internal_token}"


@router.post("/daily_event")
async def daily_event(authorization: str | None = Header(default=None)):
    # TODO: sweep agents by timezone and roll RNG for events
    internal_token = None  # could read from settings in future
    if not _authorized(internal_token, authorization):
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"ok": True}


@router.post("/semantic_refresh")
async def semantic_refresh(authorization: str | None = Header(default=None)):
    internal_token = None
    if not _authorized(internal_token, authorization):
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"ok": True}

