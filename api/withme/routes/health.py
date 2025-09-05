from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from ..db import session_scope

router = APIRouter()


@router.get("/health")
async def health():
    return {"ok": True}


@router.get("/status")
async def status():
    try:
        async with session_scope() as session:
            row = await session.execute(text("select version() as pg"))
            _ = row.scalar()
            ver = await session.execute(text("select version_num from alembic_version limit 1"))
            version = ver.scalar()
        return {"ok": True, "db": "up", "alembic": version}
    except Exception as e:
        return {"ok": False, "error": str(e)}
