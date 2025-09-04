from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .withme.routes.health import router as health_router
from .withme.routes.device import router as device_router
from .withme.routes.state import router as state_router
from .withme.routes.agent import router as agent_router
from .withme.routes.chat import router as chat_router
from .withme.routes.webhooks import router as webhooks_router
from .withme.routes.admin import router as admin_router
from .withme.routes.cron import router as cron_router
from .withme.routes.messages import router as messages_router


def create_app() -> FastAPI:
    app = FastAPI(title="With Me API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(health_router)
    app.include_router(device_router, prefix="/device", tags=["device"])
    app.include_router(state_router, tags=["state"])
    app.include_router(agent_router, prefix="/agent", tags=["agent"])
    app.include_router(chat_router, prefix="/chat", tags=["chat"])
    app.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])
    app.include_router(admin_router, prefix="/admin", tags=["admin"])
    app.include_router(cron_router, prefix="/cron", tags=["cron"])
    app.include_router(messages_router, tags=["messages"])

    # Static web test UI (optional)
    try:
        app.mount("/web", StaticFiles(directory="web", html=True), name="web")
    except Exception:
        # Web folder may not exist yet in early scaffolding.
        pass

    return app


app = create_app()
