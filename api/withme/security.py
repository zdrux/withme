from __future__ import annotations

import time
import requests
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette import status

from .config import get_settings


auth_scheme = HTTPBearer(auto_error=False)

_JWKS_CACHE: dict[str, dict] = {}
_JWKS_CACHE_AT: float | None = None


def _fetch_jwks(jwks_url: str) -> dict:
    global _JWKS_CACHE, _JWKS_CACHE_AT
    now = time.time()
    if _JWKS_CACHE and _JWKS_CACHE_AT and now - _JWKS_CACHE_AT < 300:
        return _JWKS_CACHE
    resp = requests.get(jwks_url, timeout=5)
    resp.raise_for_status()
    data = resp.json()
    _JWKS_CACHE = {j["kid"]: j for j in data.get("keys", [])}
    _JWKS_CACHE_AT = now
    return _JWKS_CACHE


def _decode_supabase_jwt(token: str) -> dict | None:
    settings = get_settings()
    # Dev bypass
    if settings.environment == "dev" and token == "dev":
        return {"sub": "00000000-0000-0000-0000-000000000000", "email": "dev@example.com"}

    # Try HS256 with SUPABASE_JWT_SECRET/TOKEN
    secret = settings.supabase_jwt_secret
    if secret:
        try:
            return jwt.decode(token, secret, algorithms=["HS256"])
        except Exception:
            pass

    # Try JWKS from Supabase project URL
    if settings.supabase_project_url:
        jwks_url = str(settings.supabase_project_url).rstrip("/") + "/auth/v1/keys"
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            jwks = _fetch_jwks(jwks_url)
            if kid and kid in jwks:
                return jwt.decode(token, key=jwks[kid], algorithms=["RS256"], options={"verify_aud": False})
        except Exception:
            pass
    return None


async def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(auth_scheme)) -> dict:
    if creds is None or not creds.scheme.lower() == "bearer" or not creds.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    claims = _decode_supabase_jwt(creds.credentials)
    if not claims:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    user_id = claims.get("sub") or claims.get("user_id") or "00000000-0000-0000-0000-000000000000"
    email = claims.get("email") or "user@example.com"
    return {"id": user_id, "email": email}
