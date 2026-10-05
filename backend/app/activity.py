"""
Append-only reservation activity timeline.
"""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from .models import ActivityLog


async def record_activity(
    db: AsyncSession,
    reservation_id: int,
    previous_state: str | None,
    new_state: str,
    reason: str,
):
    """
    Add an activity record.

    This function never commits.
    The caller's transaction controls the commit.
    """

    activity = ActivityLog(
        reservation_id=reservation_id,
        previous_state=previous_state,
        new_state=new_state,
        timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
        reason=reason,
    )

    db.add(activity)

    await db.flush()