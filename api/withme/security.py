from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette import status


auth_scheme = HTTPBearer(auto_error=False)


async def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(auth_scheme)) -> dict:
    """
    Placeholder auth dependency. In production, verify Supabase JWT and return user context.
    For now, accept any Bearer token and synthesize a user id for development/testing.
    """
    if creds is None or not creds.scheme.lower() == "bearer" or not creds.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    # TODO: Verify JWT signature and claims using Supabase.
    # Stable dev UUID for local-only flows
    return {"id": "00000000-0000-0000-0000-000000000000", "email": "dev@example.com"}
