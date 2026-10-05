from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import IdempotencyKey, User


async def get_existing_idempotency_key(
    db: AsyncSession,
    *,
    key: str,
    user: User,
    operation: str,
) -> IdempotencyKey | None:


    result = await db.execute(
        select(IdempotencyKey).where(
            IdempotencyKey.key == key,
            IdempotencyKey.user_id == user.id,
            IdempotencyKey.operation == operation,
        )
    )

    return result.scalar_one_or_none()


async def create_idempotency_record(
    db: AsyncSession,
    *,
    key: str,
    user: User,
    operation: str,
    resource_id: int | None,
) -> IdempotencyKey:

    record = IdempotencyKey(
        key=key,
        user_id=user.id,
        operation=operation,
        resource_id=resource_id,
        created_at=datetime.now(timezone.utc),
    )

    db.add(record)

    return record