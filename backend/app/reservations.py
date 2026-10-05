from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .activity import record_activity
from .config import settings
from .idempotency import claim_key, complete_key
from .models import Reservation, ReservationStatus, Seat, User, utc_now
from .realtime import manager
from .waitlist import promote_next_waitlisted_user


async def get_active_reservation_for_user(
    db: AsyncSession,
    user_id: int,
) -> Reservation | None:
    result = await db.execute(
        select(Reservation)
        .where(
            Reservation.user_id == user_id,
            Reservation.status.in_(
                [ReservationStatus.HELD, ReservationStatus.CONFIRMED]
            ),
        )
        .order_by(Reservation.created_at.desc())
    )
    return result.scalar_one_or_none()


async def hold_seat(
    db: AsyncSession,
    user: User,
    seat_id: int,
    idempotency_key: str,
) -> Reservation:
    operation = "hold"
    existing_key = await claim_key(db, idempotency_key, user.id, operation)

    if existing_key is not None:
        resource_id = existing_key.resource_id
        await db.rollback()

        if resource_id is None:
            raise HTTPException(status_code=409, detail="Previous request is still incomplete")

        result = await db.execute(select(Reservation).where(Reservation.id == resource_id))
        reservation = result.scalar_one_or_none()

        if reservation is None:
            raise HTTPException(status_code=409, detail="Original reservation no longer exists")
        if reservation.seat_id != seat_id:
            raise HTTPException(status_code=409, detail="Idempotency key was used for another seat")
        return reservation

    locked_user_result = await db.execute(
        select(User).where(User.id == user.id).with_for_update()
    )
    locked_user = locked_user_result.scalar_one()

    active = await get_active_reservation_for_user(db, locked_user.id)
    if active is not None:
        await db.rollback()
        raise HTTPException(status_code=409, detail="You already have an active reservation")

    seat_result = await db.execute(
        select(Seat).where(Seat.id == seat_id).with_for_update()
    )
    seat = seat_result.scalar_one_or_none()

    if seat is None:
        await db.rollback()
        raise HTTPException(status_code=404, detail="Seat not found")

    seat_active_result = await db.execute(
        select(Reservation).where(
            Reservation.seat_id == seat.id,
            Reservation.status.in_(
                [ReservationStatus.HELD, ReservationStatus.CONFIRMED]
            ),
        )
    )
    if seat_active_result.scalar_one_or_none() is not None:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Seat is not available")

    now = utc_now()
    reservation = Reservation(
        user_id=locked_user.id,
        seat_id=seat.id,
        status=ReservationStatus.HELD,
        held_until=now + timedelta(seconds=settings.HOLD_DURATION_SECONDS),
    )
    db.add(reservation)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Seat or user is no longer available")

    await record_activity(
        db,
        reservation.id,
        None,
        ReservationStatus.HELD.value,
        "Seat temporarily held",
    )
    await complete_key(
        db,
        idempotency_key,
        locked_user.id,
        operation,
        reservation.id,
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


async def confirm_reservation(
    db: AsyncSession,
    user: User,
    reservation_id: int,
    idempotency_key: str,
) -> Reservation:
    operation = "confirm"
    existing_key = await claim_key(db, idempotency_key, user.id, operation)

    if existing_key is not None:
        resource_id = existing_key.resource_id
        await db.rollback()

        if resource_id != reservation_id:
            raise HTTPException(status_code=409, detail="Idempotency key was used for another reservation")

        result = await db.execute(
            select(Reservation).where(
                Reservation.id == reservation_id,
                Reservation.user_id == user.id,
            )
        )
        reservation = result.scalar_one_or_none()
        if reservation is None:
            raise HTTPException(status_code=404, detail="Reservation not found")
        return reservation

    # Lock the user first so their reservation state changes are serialized.
    await db.execute(select(User).where(User.id == user.id).with_for_update())

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
        raise HTTPException(status_code=404, detail="Reservation not found")

    if reservation.status != ReservationStatus.HELD:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Only a held reservation can be confirmed")

    now = utc_now()

    if reservation.held_until is None or reservation.held_until <= now:
        reservation.status = ReservationStatus.EXPIRED

        await record_activity(
            db,
            reservation.id,
            ReservationStatus.HELD.value,
            ReservationStatus.EXPIRED.value,
            "Hold expired before confirmation",
        )

        promoted = await promote_next_waitlisted_user(db, reservation.seat_id)
        await complete_key(db, idempotency_key, user.id, operation, reservation.id)
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
                }
            )
        raise HTTPException(status_code=409, detail="Hold has expired")

    reservation.status = ReservationStatus.CONFIRMED
    reservation.confirmed_at = now

    await record_activity(
        db,
        reservation.id,
        ReservationStatus.HELD.value,
        ReservationStatus.CONFIRMED.value,
        "User confirmed reservation",
    )
    await complete_key(db, idempotency_key, user.id, operation, reservation.id)

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


async def cancel_reservation(
    db: AsyncSession,
    user: User,
    reservation_id: int,
    idempotency_key: str,
) -> Reservation:
    operation = "cancel"
    existing_key = await claim_key(db, idempotency_key, user.id, operation)

    if existing_key is not None:
        resource_id = existing_key.resource_id
        await db.rollback()

        if resource_id != reservation_id:
            raise HTTPException(status_code=409, detail="Idempotency key was used for another reservation")

        result = await db.execute(
            select(Reservation).where(
                Reservation.id == reservation_id,
                Reservation.user_id == user.id,
            )
        )
        reservation = result.scalar_one_or_none()
        if reservation is None:
            raise HTTPException(status_code=404, detail="Reservation not found")
        return reservation

    await db.execute(select(User).where(User.id == user.id).with_for_update())

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
        raise HTTPException(status_code=404, detail="Reservation not found")

    if reservation.status not in (
        ReservationStatus.HELD,
        ReservationStatus.CONFIRMED,
    ):
        await db.rollback()
        raise HTTPException(status_code=409, detail="Reservation cannot be cancelled")

    previous_state = reservation.status.value
    reservation.status = ReservationStatus.CANCELLED
    reservation.cancelled_at = utc_now()

    await record_activity(
        db,
        reservation.id,
        previous_state,
        ReservationStatus.CANCELLED.value,
        "User cancelled reservation",
    )

    promoted = await promote_next_waitlisted_user(db, reservation.seat_id)
    await complete_key(db, idempotency_key, user.id, operation, reservation.id)

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
            }
        )
    return reservation
