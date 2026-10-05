from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .activity import record_activity
from .config import settings
from .idempotency import claim_key, complete_key
from .models import (
    Reservation,
    ReservationStatus,
    Seat,
    User,
    WaitlistEntry,
    WaitlistStatus,
    utc_now,
)


# Returns the user's current active queue ticket, if any
async def get_active_waitlist_entry(db: AsyncSession, user_id: int) -> WaitlistEntry | None:
    result = await db.execute(
        select(WaitlistEntry)
        .where(
            WaitlistEntry.user_id == user_id,
            WaitlistEntry.status == WaitlistStatus.WAITING,
        )
        .order_by(WaitlistEntry.created_at, WaitlistEntry.id)
    )
    return result.scalar_one_or_none()


# Computes deterministic 1-based FIFO queue position with timestamp and ID tie-breaking
async def get_waitlist_position(db: AsyncSession, entry: WaitlistEntry) -> int:
    count = await db.scalar(
        select(func.count(WaitlistEntry.id)).where(
            WaitlistEntry.status == WaitlistStatus.WAITING,
            or_(
                WaitlistEntry.created_at < entry.created_at,
                (
                    (WaitlistEntry.created_at == entry.created_at)
                    & (WaitlistEntry.id <= entry.id)
                ),
            ),
        )
    )
    return int(count or 0)


# Enqueues user into FIFO waitlist only after verifying capacity is 100% committed
async def join_waitlist(
    db: AsyncSession,
    user: User,
    idempotency_key: str,
) -> WaitlistEntry:
    operation = "waitlist_join"
    existing_key = await claim_key(db, idempotency_key, user.id, operation)

    # Replay protection
    if existing_key is not None:
        resource_id = existing_key.resource_id
        await db.rollback()
        if resource_id is None:
            raise HTTPException(status_code=409, detail="Previous request is still incomplete")
        result = await db.execute(select(WaitlistEntry).where(WaitlistEntry.id == resource_id))
        return result.scalar_one()

    locked_user_result = await db.execute(
        select(User).where(User.id == user.id).with_for_update()
    )
    locked_user = locked_user_result.scalar_one()

    # Precondition: active ticket holders cannot queue up again
    active = await db.execute(
        select(Reservation).where(
            Reservation.user_id == locked_user.id,
            Reservation.status.in_([ReservationStatus.HELD, ReservationStatus.CONFIRMED]),
        )
    )
    if active.scalar_one_or_none() is not None:
        await db.rollback()
        raise HTTPException(status_code=409, detail="You already have an active reservation")

    existing_wait = await get_active_waitlist_entry(db, locked_user.id)
    if existing_wait is not None:
        await db.rollback()
        raise HTTPException(status_code=409, detail="You are already on the waitlist")

    # Serialize global capacity check by locking all seat rows in consistent order
    await db.execute(select(Seat).order_by(Seat.id).with_for_update())

    now = utc_now()
    occupied = await db.scalar(
        select(func.count(Reservation.id)).where(
            or_(
                Reservation.status == ReservationStatus.CONFIRMED,
                (
                    (Reservation.status == ReservationStatus.HELD)
                    & (Reservation.held_until > now)
                ),
            )
        )
    )
    total = await db.scalar(select(func.count(Seat.id)))

    # Reject joining waitlist if open inventory remains
    if int(occupied or 0) < int(total or 0):
        await db.rollback()
        raise HTTPException(status_code=409, detail="Seats are still available")

    entry = WaitlistEntry(
        user_id=locked_user.id,
        status=WaitlistStatus.WAITING,
    )
    db.add(entry)
    await db.flush()

    await complete_key(db, idempotency_key, locked_user.id, operation, entry.id)
    await db.commit()
    await db.refresh(entry)
    return entry


# Opt-out endpoint to relinquish waitlist queue spot
async def cancel_waitlist(
    db: AsyncSession,
    user: User,
    entry_id: int,
    idempotency_key: str,
) -> WaitlistEntry:
    operation = "waitlist_cancel"
    existing_key = await claim_key(db, idempotency_key, user.id, operation)

    if existing_key is not None:
        resource_id = existing_key.resource_id
        await db.rollback()
        result = await db.execute(
            select(WaitlistEntry).where(
                WaitlistEntry.id == resource_id,
                WaitlistEntry.user_id == user.id,
            )
        )
        entry = result.scalar_one_or_none()
        if entry is None:
            raise HTTPException(status_code=404, detail="Waitlist entry not found")
        return entry

    result = await db.execute(
        select(WaitlistEntry)
        .where(
            WaitlistEntry.id == entry_id,
            WaitlistEntry.user_id == user.id,
        )
        .with_for_update()
    )
    entry = result.scalar_one_or_none()

    if entry is None:
        await db.rollback()
        raise HTTPException(status_code=404, detail="Waitlist entry not found")

    if entry.status != WaitlistStatus.WAITING:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Waitlist entry is not active")

    entry.status = WaitlistStatus.CANCELLED
    entry.cancelled_at = utc_now()
    await complete_key(db, idempotency_key, user.id, operation, entry.id)
    await db.commit()
    await db.refresh(entry)
    return entry


# Reallocates a freed seat to the head of the waitlist.
# Loops to automatically prune candidates who already managed to obtain seats elsewhere.
async def promote_next_waitlisted_user(
    db: AsyncSession,
    seat_id: int,
) -> Reservation | None:
    while True:
        # Non-blocking lock on head candidate to prevent worker deadlocks
        result = await db.execute(
            select(WaitlistEntry)
            .where(WaitlistEntry.status == WaitlistStatus.WAITING)
            .order_by(WaitlistEntry.created_at, WaitlistEntry.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        entry = result.scalar_one_or_none()

        if entry is None:
            return None

        user_result = await db.execute(
            select(User).where(User.id == entry.user_id).with_for_update()
        )
        user = user_result.scalar_one()

        # Invalidate entry if user holds an active seat from another path
        active_result = await db.execute(
            select(Reservation).where(
                Reservation.user_id == user.id,
                Reservation.status.in_(
                    [ReservationStatus.HELD, ReservationStatus.CONFIRMED]
                ),
            )
        )
        if active_result.scalar_one_or_none() is not None:
            entry.status = WaitlistStatus.CANCELLED
            entry.cancelled_at = utc_now()
            await db.flush()
            continue

        await db.execute(select(Seat).where(Seat.id == seat_id).with_for_update())

        # Grant candidate a temporary lease
        now = utc_now()
        reservation = Reservation(
            user_id=user.id,
            seat_id=seat_id,
            status=ReservationStatus.HELD,
            held_until=now + timedelta(seconds=settings.HOLD_DURATION_SECONDS),
        )
        db.add(reservation)
        await db.flush()

        entry.status = WaitlistStatus.PROMOTED
        entry.promoted_at = now

        await record_activity(
            db,
            reservation.id,
            None,
            ReservationStatus.HELD.value,
            "Promoted from FIFO waitlist",
        )
        await db.flush()
        return reservation