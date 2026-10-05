"""
Idempotency handling for SeatLock.

An idempotency key ensures that retrying the same state-changing
request does not create a second reservation or waitlist entry.
"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .models import IdempotencyKey


async def begin_idempotent_operation(
    db: AsyncSession,
    key: str,
    user_id: int,
    operation: str,
) -> IdempotencyKey | None:
    """
    Attempt to claim an idempotency key.

    Returns:
        None:
            This request successfully claimed the key and may continue.

        Existing IdempotencyKey:
            The operation was already processed previously.
    """

    statement = (
        insert(IdempotencyKey)
        .values(
            key=key,
            user_id=user_id,
            operation=operation,
            resource_id=None,
        )
        .on_conflict_do_nothing(
            index_elements=[
                "key",
                "user_id",
                "operation",
            ]
        )
        .returning(IdempotencyKey.id)
    )

    result = await db.execute(statement)

    inserted_id = result.scalar_one_or_none()

    # We successfully inserted the idempotency record.
    if inserted_id is not None:
        return None

    # The key already exists.
    result = await db.execute(
        select(IdempotencyKey).where(
            IdempotencyKey.key == key,
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.operation == operation,
        )
    )

    existing = result.scalar_one_or_none()

    return existing


async def complete_idempotent_operation(
    db: AsyncSession,
    key: str,
    user_id: int,
    operation: str,
    resource_id: int,
):
    """
    Associate the idempotency record with the resource created
    by the operation.

    Example:

        Idempotency-Key: abc123
                    ↓
        Reservation ID: 17

    A retry using abc123 can therefore return reservation 17
    instead of creating another reservation.
    """

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