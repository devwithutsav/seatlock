from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import IdempotencyKey


# Atomically claims an idempotency key.
# Returns None on successful insert (caller proceeds), or the existing record if already claimed.
async def claim_key(
    db: AsyncSession,
    key: str,
    user_id: int,
    operation: str,
) -> IdempotencyKey | None:
    statement = (
        insert(IdempotencyKey)
        .values(
            key=key,
            user_id=user_id,
            operation=operation,
            resource_id=None,
        )
        .on_conflict_do_nothing(
            constraint="uq_idempotency_key_user_operation"
        )
        .returning(IdempotencyKey.id)
    )

    result = await db.execute(statement)
    inserted = result.scalar_one_or_none()

    if inserted is not None:
        return None

    # Fetch existing row to evaluate replay status or in-flight collision
    existing = await db.execute(
        select(IdempotencyKey).where(
            IdempotencyKey.key == key,
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.operation == operation,
        )
    )
    return existing.scalar_one()


# Attaches created/mutated resource ID to key record once operation successfully completes
async def complete_key(
    db: AsyncSession,
    key: str,
    user_id: int,
    operation: str,
    resource_id: int,
) -> None:
    result = await db.execute(
        select(IdempotencyKey)
        .where(
            IdempotencyKey.key == key,
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.operation == operation,
        )
        .with_for_update()
    )
    record = result.scalar_one()
    record.resource_id = resource_id
    await db.flush()