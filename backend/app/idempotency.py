from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import IdempotencyKey


async def get_existing_idempotency_key(
    db: AsyncSession,
    key: str,
    user_id: int,
    operation: str,
):

    result = await db.execute(
        select(IdempotencyKey).where(
            IdempotencyKey.key == key,
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.operation == operation,
        )
    )

    return result.scalar_one_or_none()


async def create_idempotency_record(
    db: AsyncSession,
    key: str,
    user_id: int,
    operation: str,
    resource_id: int | None,
):

    record = IdempotencyKey(
        key=key,
        user_id=user_id,
        operation=operation,
        resource_id=resource_id,
    )

    db.add(record)

    await db.flush()

    return record