"""
Core reservation state machine.

All state-changing reservation operations are transactional.
"""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
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
)
from .realtime import manager
from .waitlist import (
    promote_next_waitlisted_user,
)


HOLD_DURATION_SECONDS = 60


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Active reservation lookup
# ---------------------------------------------------------------------------

async def get_active_reservation_for_user(
    db: AsyncSession,
    user_id: int,
):
    result = await db.execute(
        select(Reservation)
        .where(
            Reservation.user_id == user_id,
            Reservation.status.in_(
                [
                    ReservationStatus.HELD,
                    ReservationStatus.CONFIRMED,
                ]
            ),
        )
        .order_by(
            Reservation.created_at.desc()
        )
    )

    return result.scalar_one_or_none()


async def get_active_reservation_for_seat(
    db: AsyncSession,
    seat_id: int,
):
    result = await db.execute(
        select(Reservation)
        .where(
            Reservation.seat_id == seat_id,
            Reservation.status.in_(
                [
                    ReservationStatus.HELD,
                    ReservationStatus.CONFIRMED,
                ]
            ),
        )
        .order_by(
            Reservation.created_at.desc()
        )
    )

    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Hold
# ---------------------------------------------------------------------------

async def hold_seat(
    db: AsyncSession,
    user: User,
    seat_id: int,
    idempotency_key: str,
):

    operation = "hold"

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
            select(Reservation)
            .where(
                Reservation.id == resource_id
            )
        )

        reservation = result.scalar_one_or_none()

        if reservation is None:
            raise HTTPException(
                status_code=409,
                detail="Idempotent reservation no longer exists",
            )

        if reservation.seat_id != seat_id:

            raise HTTPException(
                status_code=409,
                detail="Idempotency key was already used for another seat",
            )

        return reservation


    # Lock user first.
    user_result = await db.execute(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
    )

    locked_user = user_result.scalar_one()


    # One active reservation per user.
    existing_reservation = (
        await get_active_reservation_for_user(
            db,
            locked_user.id,
        )
    )

    if existing_reservation is not None:

        await db.rollback()

        raise HTTPException(
            status_code=409,
            detail="User already has an active reservation",
        )


    # Lock the requested seat.
    seat_result = await db.execute(
        select(Seat)
        .where(Seat.id == seat_id)
        .with_for_update()
    )

    seat = seat_result.scalar_one_or_none()

    if seat is None:

        await db.rollback()

        raise HTTPException(
            status_code=404,
            detail="Seat not found",
        )


    existing_seat_reservation = (
        await get_active_reservation_for_seat(
            db,
            seat.id,
        )
    )

    if existing_seat_reservation is not None:

        await db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Seat is not available",
        )


    now = utc_now()

    reservation = Reservation(
        user_id=locked_user.id,
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


    await record_activity(
        db=db,
        reservation_id=reservation.id,
        previous_state=None,
        new_state=ReservationStatus.HELD.value,
        reason="Seat temporarily held",
    )


    await complete_idempotent_operation(
        db=db,
        key=idempotency_key,
        user_id=locked_user.id,
        operation=operation,
        resource_id=reservation.id,
    )


    await db.commit()

    await db.refresh(reservation)

    await manager.broadcast(
        {
            "type": "reservation_changed",
            "reservation_id": reservation.id,
            "seat_id": reservation.seat_id,
            "status": reservation.status.value,
        }
    )

    return reservation


# ---------------------------------------------------------------------------
# Confirm
# ---------------------------------------------------------------------------

async def confirm_reservation(
    db: AsyncSession,
    user: User,
    reservation_id: int,
    idempotency_key: str,
):

    operation = "confirm"

    existing = await begin_idempotent_operation(
        db=db,
        key=idempotency_key,
        user_id=user.id,
        operation=operation,
    )

    if existing is not None:

        if existing.resource_id != reservation_id:

            await db.rollback()

            raise HTTPException(
                status_code=409,
                detail="Idempotency key was already used for another reservation",
            )

        await db.rollback()

        result = await db.execute(
            select(Reservation)
            .where(
                Reservation.id == reservation_id,
                Reservation.user_id == user.id,
            )
        )

        reservation = result.scalar_one_or_none()

        if reservation is None:
            raise HTTPException(
                status_code=404,
                detail="Reservation not found",
            )

        return reservation


    # Lock user first.
    await db.execute(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
    )


    result = await db.execute(
        select(Reservation)
        .where(
            Reservation.id == reservation_id,
            Reservation.user_id == user.id,
        )
        .with_for_update()
    )

    reservation = result.scalar_one_or_none()

    if reservation is None:

        await db.rollback()

        raise HTTPException(
            status_code=404,
            detail="Reservation not found",
        )


    if reservation.status != ReservationStatus.HELD:

        await db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Only a held reservation can be confirmed",
        )


    now = utc_now()

    if (
        reservation.held_until is None
        or reservation.held_until <= now
    ):

        reservation.status = (
            ReservationStatus.EXPIRED
        )

        await record_activity(
            db=db,
            reservation_id=reservation.id,
            previous_state=ReservationStatus.HELD.value,
            new_state=ReservationStatus.EXPIRED.value,
            reason="Hold expired before confirmation",
        )


        promoted = (
            await promote_next_waitlisted_user(
                db,
                reservation.seat_id,
            )
        )


        await complete_idempotent_operation(
            db=db,
            key=idempotency_key,
            user_id=user.id,
            operation=operation,
            resource_id=reservation.id,
        )


        await db.commit()


        await manager.broadcast(
            {
                "type": "reservation_expired",
                "reservation_id": reservation.id,
                "seat_id": reservation.seat_id,
            }
        )

        if promoted is not None:

            await manager.broadcast(
                {
                    "type": "waitlist_promoted",
                    "reservation_id": promoted.id,
                    "seat_id": promoted.seat_id,
                    "user_id": promoted.user_id,
                }
            )


        raise HTTPException(
            status_code=409,
            detail="Hold has expired",
        )


    reservation.status = (
        ReservationStatus.CONFIRMED
    )

    reservation.confirmed_at = now


    await record_activity(
        db=db,
        reservation_id=reservation.id,
        previous_state=ReservationStatus.HELD.value,
        new_state=ReservationStatus.CONFIRMED.value,
        reason="User confirmed reservation",
    )


    await complete_idempotent_operation(
        db=db,
        key=idempotency_key,
        user_id=user.id,
        operation=operation,
        resource_id=reservation.id,
    )


    await db.commit()

    await db.refresh(reservation)

    await manager.broadcast(
        {
            "type": "reservation_confirmed",
            "reservation_id": reservation.id,
            "seat_id": reservation.seat_id,
        }
    )

    return reservation


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------

async def cancel_reservation(
    db: AsyncSession,
    user: User,
    reservation_id: int,
    idempotency_key: str,
):

    operation = "cancel"

    existing = await begin_idempotent_operation(
        db=db,
        key=idempotency_key,
        user_id=user.id,
        operation=operation,
    )

    if existing is not None:

        if existing.resource_id != reservation_id:

            await db.rollback()

            raise HTTPException(
                status_code=409,
                detail="Idempotency key was already used for another reservation",
            )

        await db.rollback()

        result = await db.execute(
            select(Reservation)
            .where(
                Reservation.id == reservation_id,
                Reservation.user_id == user.id,
            )
        )

        reservation = result.scalar_one_or_none()

        if reservation is None:
            raise HTTPException(
                status_code=404,
                detail="Reservation not found",
            )

        return reservation


    # Lock user.
    await db.execute(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
    )


    result = await db.execute(
        select(Reservation)
        .where(
            Reservation.id == reservation_id,
            Reservation.user_id == user.id,
        )
        .with_for_update()
    )

    reservation = result.scalar_one_or_none()

    if reservation is None:

        await db.rollback()

        raise HTTPException(
            status_code=404,
            detail="Reservation not found",
        )


    if reservation.status not in (
        ReservationStatus.HELD,
        ReservationStatus.CONFIRMED,
    ):

        await db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Reservation cannot be cancelled",
        )


    previous_state = reservation.status.value

    reservation.status = (
        ReservationStatus.CANCELLED
    )

    reservation.cancelled_at = utc_now()


    await record_activity(
        db=db,
        reservation_id=reservation.id,
        previous_state=previous_state,
        new_state=ReservationStatus.CANCELLED.value,
        reason="User cancelled reservation",
    )


    # Promote next FIFO waitlisted user.
    promoted = (
        await promote_next_waitlisted_user(
            db,
            reservation.seat_id,
        )
    )


    await complete_idempotent_operation(
        db=db,
        key=idempotency_key,
        user_id=user.id,
        operation=operation,
        resource_id=reservation.id,
    )


    await db.commit()

    await db.refresh(reservation)


    await manager.broadcast(
        {
            "type": "reservation_cancelled",
            "reservation_id": reservation.id,
            "seat_id": reservation.seat_id,
        }
    )


    if promoted is not None:

        await manager.broadcast(
            {
                "type": "waitlist_promoted",
                "reservation_id": promoted.id,
                "seat_id": promoted.seat_id,
                "user_id": promoted.user_id,
            }
        )


    return reservation