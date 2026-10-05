from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings


# Async SQLAlchemy engine with connection health checks enabled
engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=False,
)

# Shared session factory configured for explicit commits and async hygiene
SessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


# Per-request DB session dependency with automated rollback on unhandled exceptions
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise