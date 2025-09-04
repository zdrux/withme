from functools import lru_cache
from pydantic import AnyUrl
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    environment: str = "dev"

    # Database
    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/withme"

    # External services
    openai_api_key: str | None = None
    pinecone_api_key: str | None = None
    supabase_url: AnyUrl | None = None
    supabase_jwt_secret: str | None = None
    redis_url: str | None = "redis://localhost:6379/0"
    fal_api_key: str | None = None
    fcm_server_key: str | None = None

    # API behavior
    image_affinity_threshold: float = 0.60
    initiation_daily_cap: int = 2

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[arg-type]
