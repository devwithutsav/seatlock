"""
SQLAlchemy database models for SeatLock.
"""

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from .database import Base


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ReservationStatus(str, Enum):
    HELD = "HELD"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class WaitlistStatus(str, Enum):
    WAITING = "WAITING"
    PROMOTED = "PROMOTED"
    CANCELLED = "CANCELLED"


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    reservations: Mapped[list["Reservation"]] = relationship(
        back_populates="user",
    )

    waitlist_entries: Mapped[list["WaitlistEntry"]] = relationship(
        back_populates="user",
    )


# ---------------------------------------------------------------------------
# Seat
# ---------------------------------------------------------------------------

class Seat(Base):
    __tablename__ = "seats"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    seat_number: Mapped[int] = mapped_column(
        unique=True,
        nullable=False,
    )

    reservations: Mapped[list["Reservation"]] = relationship(
        back_populates="seat",
    )


# ---------------------------------------------------------------------------
# Reservation
# ---------------------------------------------------------------------------

class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    seat_id: Mapped[int] = mapped_column(
        ForeignKey("seats.id"),
        nullable=False,
        index=True,
    )

    status: Mapped[ReservationStatus] = mapped_column(
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        default=utc_now,
        nullable=False,
    )

    held_until: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )

    confirmed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )

    cancelled_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )

    user: Mapped["User"] = relationship(
        back_populates="reservations",
    )

    seat: Mapped["Seat"] = relationship(
        back_populates="reservations",
    )

    activities: Mapped[list["ActivityLog"]] = relationship(
        back_populates="reservation",
        order_by="ActivityLog.timestamp",
    )

    __table_args__ = (
        Index(
            "ix_reservation_user_status",
            "user_id",
            "status",
        ),
        Index(
            "ix_reservation_seat_status",
            "seat_id",
            "status",
        ),
    )


# ---------------------------------------------------------------------------
# Waitlist
# ---------------------------------------------------------------------------

class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    status: Mapped[WaitlistStatus] = mapped_column(
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        default=utc_now,
        nullable=False,
    )

    user: Mapped["User"] = relationship(
        back_populates="waitlist_entries",
    )

    __table_args__ = (
        Index(
            "ix_waitlist_user_status",
            "user_id",
            "status",
        ),
        Index(
            "ix_waitlist_status_created",
            "status",
            "created_at",
        ),
    )


# ---------------------------------------------------------------------------
# Activity log
# ---------------------------------------------------------------------------

class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    reservation_id: Mapped[int] = mapped_column(
        ForeignKey("reservations.id"),
        nullable=False,
        index=True,
    )

    previous_state: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    new_state: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    timestamp: Mapped[datetime] = mapped_column(
        default=utc_now,
        nullable=False,
    )

    reason: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    reservation: Mapped["Reservation"] = relationship(
        back_populates="activities",
    )


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    operation: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    resource_id: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        default=utc_now,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "key",
            "user_id",
            "operation",
            name="uq_idempotency_key",
        ),
    )