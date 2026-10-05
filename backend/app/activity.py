from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from .models import ActivityLog, Reservation


async def record_activity(
    db: AsyncSession,
    reservation: Reservation,
    previous_state: str | None,
    new_state: str,
    reason: str,
) -> ActivityLog:

    activity = ActivityLog(
        reservation_id=reservation.id,
        previous_state=previous_state,
        new_state=new_state,
        timestamp=datetime.now(timezone.utc),
        reason=reason,
    )

    db.add(activity)

    return activity