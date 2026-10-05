import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import SessionLocal
from .models import Reservation, ReservationStatus


# How frequently the background worker checks for expired
# reservations.
EXPIRY_CHECK_INTERVAL = 5


async def expire_holds():
    """
    Background task that periodically looks for expired
    temporary holds.

    The actual transition and waitlist promotion logic will
    be implemented alongside the reservation service.
    """

    while True:

        async with SessionLocal() as db:

            # We will implement the actual expiry logic here.
            #
            # Conceptually:
            #
            # HELD
            #   +
            # held_until < now
            #   ↓
            # EXPIRED
            #
            # Then:
            #
            # EXPIRED
            #   ↓
            # promote next waitlisted user

            await db.commit()

        await asyncio.sleep(EXPIRY_CHECK_INTERVAL)