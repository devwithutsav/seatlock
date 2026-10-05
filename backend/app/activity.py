from sqlalchemy.ext.asyncio import AsyncSession

from .models import ActivityLog


# Records state transitions for audit trails within the active transaction.
# Uses db.flush() so the record gets an ID/persists without committing outer work.
async def record_activity(
    db: AsyncSession,
    reservation_id: int,
    previous_state: str | None,
    new_state: str,
    reason: str,
) -> None:
    db.add(
        ActivityLog(
            reservation_id=reservation_id,
            previous_state=previous_state,
            new_state=new_state,
            reason=reason,
        )
    )
    await db.flush()