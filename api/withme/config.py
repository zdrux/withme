from functools import lru_cache
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")
    environment: str = "dev"

    # Database
    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/withme"

    # External services
    openai_api_key: str | None = None
    pinecone_api_key: str | None = Field(default=None, validation_alias=AliasChoices("PINECONE_API_KEY", "PINE_CONE_API_KEY"))
    supabase_url: str | None = None
    supabase_project_url: str | None = None
    supabase_jwt_secret: str | None = Field(default=None, validation_alias=AliasChoices("SUPABASE_JWT_SECRET", "SUPABASE_JWT_TOKEN"))
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None
    redis_url: str | None = "redis://localhost:6379/0"
    fal_api_key: str | None = Field(default=None, validation_alias=AliasChoices("FAL_API_KEY", "FALAI_API_KEY"))
    fcm_server_key: str | None = None
    cron_token: str | None = None

    # API behavior
    image_affinity_threshold: float = 0.60
    initiation_daily_cap: int = 2

    # Pydantic v2: model_config above replaces legacy Config


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[arg-type]
