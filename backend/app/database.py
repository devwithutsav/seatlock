"""Database and application configuration for SeatLock."""

from collections.abc import AsyncGenerator
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Settings(BaseSettings):
    DATABASE_URL: str
    FRONTEND_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    SESSION_TTL_SECONDS: int = 60 * 60 * 24

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def frontend_origins(self) -> list[str]:
        return [
            origin.strip().rstrip("/")
            for origin in self.FRONTEND_ORIGINS.split(",")
            if origin.strip()
        ]


settings = Settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide one AsyncSession per request and roll back on failure."""
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
