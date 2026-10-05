import asyncio

from sqlalchemy import select

from .activity import record_activity
from .database import SessionLocal
from .models import Reservation, ReservationStatus, utc_now
from .realtime import manager
from .waitlist import promote_next_waitlisted_user


# Batch worker pass: cleans up stale holds and advances waitlisted candidates.
# Uses `FOR UPDATE SKIP LOCKED` to allow safe multi-worker/process execution without deadlocks.
async def expire_holds_once() -> int:
    async with SessionLocal() as db:
        now = utc_now()

        result = await db.execute(
            select(Reservation)
            .where(
                Reservation.status == ReservationStatus.HELD,
                Reservation.held_until <= now,
            )
            .order_by(Reservation.held_until, Reservation.id)
            .limit(100)
            .with_for_update(skip_locked=True)
        )
        expired = result.scalars().all()

        promoted = []

        for reservation in expired:
            reservation.status = ReservationStatus.EXPIRED

            await record_activity(
                db,
                reservation.id,
                ReservationStatus.HELD.value,
                ReservationStatus.EXPIRED.value,
                "Hold expired automatically",
            )

            # Instantly reallocate freed seat to waitlist in same transaction
            next_reservation = await promote_next_waitlisted_user(
                db,
                reservation.seat_id,
            )
            if next_reservation is not None:
                promoted.append(next_reservation)

        await db.commit()

        # Broadcast events after commit to avoid notifying on rolled-back state
        for reservation in expired:
            await manager.broadcast(
                {
                    "type": "reservation_expired",
                    "reservation_id": reservation.id,
                    "seat_id": reservation.seat_id,
                }
            )

        for reservation in promoted:
            await manager.broadcast(
                {
                    "type": "waitlist_promoted",
                    "reservation_id": reservation.id,
                    "seat_id": reservation.seat_id,
                }
            )

        return len(expired)


# Background loop running tick-based hold sweeps
async def expiry_worker() -> None:
    while True:
        try:
            await expire_holds_once()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # Prevent background loop crash on transient DB errors
            print(f"[expiry-worker] {type(exc).__name__}: {exc}")

        await asyncio.sleep(1)