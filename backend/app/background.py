"""
Background expiry worker.

Because expiration is stored in PostgreSQL as held_until,
expired holds can be recovered even after a server restart.
"""

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from .activity import record_activity
from .database import SessionLocal
from .models import (
    Reservation,
    ReservationStatus,
    User,
)
from .realtime import manager
from .waitlist import (
    promote_next_waitlisted_user,
)


async def expire_holds_once():
    """
    Release expired reservations and promote the next waitlisted users.
    """

    async with SessionLocal() as db:

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        result = await db.execute(
            select(Reservation)
            .join(
                User,
                User.id == Reservation.user_id,
            )
            .where(
                Reservation.status
                == ReservationStatus.HELD,
                Reservation.held_until <= now,
            )
            .order_by(
                Reservation.held_until,
                Reservation.id,
            )
            .limit(100)
            .with_for_update(
                skip_locked=True
            )
        )

        expired = result.scalars().all()

        promoted_reservations = []

        for reservation in expired:

            if (
                reservation.status
                != ReservationStatus.HELD
            ):
                continue


            reservation.status = (
                ReservationStatus.EXPIRED
            )


            await record_activity(
                db=db,
                reservation_id=reservation.id,
                previous_state=ReservationStatus.HELD.value,
                new_state=ReservationStatus.EXPIRED.value,
                reason="Hold expired automatically",
            )


            promoted = (
                await promote_next_waitlisted_user(
                    db,
                    reservation.seat_id,
                )
            )

            if promoted is not None:
                promoted_reservations.append(
                    promoted
                )


        await db.commit()


        # Broadcast only after the transaction succeeds.
        for reservation in expired:

            await manager.broadcast(
                {
                    "type": "reservation_expired",
                    "reservation_id": reservation.id,
                    "seat_id": reservation.seat_id,
                }
            )


        for reservation in promoted_reservations:

            await manager.broadcast(
                {
                    "type": "waitlist_promoted",
                    "reservation_id": reservation.id,
                    "seat_id": reservation.seat_id,
                    "user_id": reservation.user_id,
                }
            )


async def expire_holds():
    """
    Run expiry checks continuously.
    """

    while True:

        try:

            await expire_holds_once()

        except asyncio.CancelledError:
            raise

        except Exception as exc:

            print(
                f"Expiry worker error: {exc}"
            )

        await asyncio.sleep(1)