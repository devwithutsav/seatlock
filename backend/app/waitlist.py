"""
FIFO waitlist implementation.
"""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import (
    func,
    or_,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from .activity import record_activity
from .idempotency import (
    begin_idempotent_operation,
    complete_idempotent_operation,
)
from .models import (
    Reservation,
    ReservationStatus,
    Seat,
    User,
    WaitlistEntry,
    WaitlistStatus,
)
from .realtime import manager


HOLD_DURATION_SECONDS = 60


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def get_active_waitlist_entry(
    db: AsyncSession,
    user_id: int,
):
    result = await db.execute(
        select(WaitlistEntry)
        .where(
            WaitlistEntry.user_id == user_id,
            WaitlistEntry.status
            == WaitlistStatus.WAITING,
        )
        .order_by(
            WaitlistEntry.created_at,
            WaitlistEntry.id,
        )
    )

    return result.scalar_one_or_none()


async def get_waitlist_position(
    db: AsyncSession,
    entry: WaitlistEntry,
) -> int:

    result = await db.execute(
        select(func.count(WaitlistEntry.id))
        .where(
            WaitlistEntry.status
            == WaitlistStatus.WAITING,
            or_(
                WaitlistEntry.created_at
                < entry.created_at,

                (
                    WaitlistEntry.created_at
                    == entry.created_at
                )
                & (
                    WaitlistEntry.id
                    <= entry.id
                ),
            ),
        )
    )

    return int(
        result.scalar_one()
    )


# ---------------------------------------------------------------------------
# Join waitlist
# ---------------------------------------------------------------------------

async def join_waitlist(
    db: AsyncSession,
    user: User,
    idempotency_key: str,
):
    operation = "waitlist_join"

    existing = await begin_idempotent_operation(
        db=db,
        key=idempotency_key,
        user_id=user.id,
        operation=operation,
    )

    if existing is not None:

        resource_id = existing.resource_id
        await db.rollback()

        if resource_id is None:
            raise HTTPException(
                status_code=409,
                detail="Idempotency operation is incomplete",
            )

        result = await db.execute(
            select(WaitlistEntry)
            .where(WaitlistEntry.id == resource_id)
        )

        return result.scalar_one()


    # Serialize operations for this user.
    user_result = await db.execute(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
    )

    locked_user = user_result.scalar_one()


    # A user with an active reservation should not waitlist.
    active_result = await db.execute(
        select(Reservation)
        .where(
            Reservation.user_id == locked_user.id,
            Reservation.status.in_(
                [
                    ReservationStatus.HELD,
                    ReservationStatus.CONFIRMED,
                ]
            ),
        )
    )

    active_reservation = (
        active_result.scalar_one_or_none()
    )

    if active_reservation is not None:

        await db.rollback()

        raise HTTPException(
            status_code=409,
            detail="User already has an active reservation",
        )


    # Lock all 20 seat rows while determining whether the
    # workshop is actually full.
    await db.execute(
        select(Seat)
        .with_for_update()
    )


    total_result = await db.execute(
        select(func.count(Seat.id))
    )

    total_seats = total_result.scalar_one()


    occupied_result = await db.execute(
        select(func.count(Reservation.id))
        .where(
            Reservation.status.in_(
                [
                    ReservationStatus.HELD,
                    ReservationStatus.CONFIRMED,
                ]
            )
        )
    )

    occupied_seats = occupied_result.scalar_one()


    if occupied_seats < total_seats:

        await db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Seats are available; use the reservation endpoint",
        )


    existing_entry = (
        await get_active_waitlist_entry(
            db,
            locked_user.id,
        )
    )

    if existing_entry is not None:

        await db.rollback()

        raise HTTPException(
            status_code=409,
            detail="User is already on the waitlist",
        )


    entry = WaitlistEntry(
        user_id=locked_user.id,
        status=WaitlistStatus.WAITING,
    )

    db.add(entry)

    await db.flush()


    await complete_idempotent_operation(
        db=db,
        key=idempotency_key,
        user_id=locked_user.id,
        operation=operation,
        resource_id=entry.id,
    )


    await db.commit()

    await db.refresh(entry)

    await manager.broadcast(
        {
            "type": "waitlist_changed",
        }
    )

    return entry


# ---------------------------------------------------------------------------
# Cancel waitlist entry
# ---------------------------------------------------------------------------

async def cancel_waitlist(
    db: AsyncSession,
    user: User,
    entry_id: int,
    idempotency_key: str,
):

    operation = "waitlist_cancel"

    existing = await begin_idempotent_operation(
        db=db,
        key=idempotency_key,
        user_id=user.id,
        operation=operation,
    )

    if existing is not None:

        if (
            existing.resource_id is not None
            and existing.resource_id != entry_id
        ):
            await db.rollback()

            raise HTTPException(
                status_code=409,
                detail="Idempotency key already used for another entry",
            )

        await db.rollback()

        result = await db.execute(
            select(WaitlistEntry)
            .where(
                WaitlistEntry.id == entry_id,
                WaitlistEntry.user_id == user.id,
            )
        )

        return result.scalar_one()


    user_result = await db.execute(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
    )

    locked_user = user_result.scalar_one()


    result = await db.execute(
        select(WaitlistEntry)
        .where(
            WaitlistEntry.id == entry_id,
            WaitlistEntry.user_id == locked_user.id,
        )
        .with_for_update()
    )

    entry = result.scalar_one_or_none()

    if entry is None:

        await db.rollback()

        raise HTTPException(
            status_code=404,
            detail="Waitlist entry not found",
        )


    if entry.status != WaitlistStatus.WAITING:

        await db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Waitlist entry is no longer active",
        )


    entry.status = WaitlistStatus.CANCELLED


    await complete_idempotent_operation(
        db=db,
        key=idempotency_key,
        user_id=locked_user.id,
        operation=operation,
        resource_id=entry.id,
    )


    await db.commit()

    await db.refresh(entry)

    await manager.broadcast(
        {
            "type": "waitlist_changed",
        }
    )

    return entry


# ---------------------------------------------------------------------------
# Promote next user
# ---------------------------------------------------------------------------

async def promote_next_waitlisted_user(
    db: AsyncSession,
    seat_id: int,
):
    """
    Promote the next eligible FIFO user into a temporary hold.

    Must be called from an existing transaction.
    """

    while True:

        result = await db.execute(
            select(WaitlistEntry)
            .where(
                WaitlistEntry.status
                == WaitlistStatus.WAITING
            )
            .order_by(
                WaitlistEntry.created_at,
                WaitlistEntry.id,
            )
            .limit(1)
            .with_for_update()
        )

        entry = result.scalar_one_or_none()

        if entry is None:
            return None


        # Lock the candidate user.
        user_result = await db.execute(
            select(User)
            .where(User.id == entry.user_id)
            .with_for_update()
        )

        candidate = user_result.scalar_one()


        # Candidate may no longer be eligible.
        active_result = await db.execute(
            select(Reservation)
            .where(
                Reservation.user_id
                == candidate.id,
                Reservation.status.in_(
                    [
                        ReservationStatus.HELD,
                        ReservationStatus.CONFIRMED,
                    ]
                ),
            )
        )

        active = (
            active_result.scalar_one_or_none()
        )

        if active is not None:

            entry.status = WaitlistStatus.CANCELLED

            await db.flush()

            continue


        # Lock the seat before creating the promotion.
        seat_result = await db.execute(
            select(Seat)
            .where(Seat.id == seat_id)
            .with_for_update()
        )

        seat = seat_result.scalar_one_or_none()

        if seat is None:
            return None


        # Verify that the seat is really free.
        active_seat_result = await db.execute(
            select(Reservation)
            .where(
                Reservation.seat_id == seat.id,
                Reservation.status.in_(
                    [
                        ReservationStatus.HELD,
                        ReservationStatus.CONFIRMED,
                    ]
                ),
            )
        )

        active_seat = (
            active_seat_result.scalar_one_or_none()
        )

        if active_seat is not None:
            return None


        now = datetime.now(timezone.utc).replace(tzinfo=None)

        reservation = Reservation(
            user_id=candidate.id,
            seat_id=seat.id,
            status=ReservationStatus.HELD,
            created_at=now,
            held_until=(
                now
                + timedelta(
                    seconds=HOLD_DURATION_SECONDS
                )
            ),
        )

        db.add(reservation)

        await db.flush()


        entry.status = WaitlistStatus.PROMOTED

        await record_activity(
            db=db,
            reservation_id=reservation.id,
            previous_state=None,
            new_state=ReservationStatus.HELD.value,
            reason="Promoted from FIFO waitlist",
        )

        await db.flush()

        return reservation