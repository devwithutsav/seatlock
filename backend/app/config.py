from functools import lru_cache
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


# Application settings loaded from env vars with async PG dialect normalization
class Settings(BaseSettings):
    DATABASE_URL: str
    FRONTEND_ORIGINS: str = "http://localhost:5173"
    HOLD_DURATION_SECONDS: int = 300
    SESSION_DAYS: int = 7

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Source order (highest priority first): init kwargs, system env vars, .env file, secrets.
    # The .env file is only a fallback and is optional, so deployed environments such as
    # Railway rely on real environment variables.
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings, env_settings, dotenv_settings, file_secret_settings)

    # Ensures standard 'postgres://' URLs (e.g. from Heroku/Railway) use the asyncpg driver
    @property
    def database_url(self) -> str:
        url = self.DATABASE_URL.strip()
        if url.startswith("postgres://"):
            return "postgresql+asyncpg://" + url[len("postgres://"):]
        if url.startswith("postgresql://") and "+asyncpg" not in url:
            return "postgresql+asyncpg://" + url[len("postgresql://"):]
        return url

    # Comma-separated CORS origin parser
    @property
    def frontend_origins(self) -> list[str]:
        return [origin.strip() for origin in self.FRONTEND_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()