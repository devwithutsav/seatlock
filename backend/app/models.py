from datetime import datetime
from enum import Enum

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class ReservationStatus(str, Enum):

    HELD = "HELD"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class WaitlistStatus(str, Enum):

    WAITING = "WAITING"
    PROMOTED = "PROMOTED"
    CANCELLED = "CANCELLED"


class User(Base):

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
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


class Seat(Base):

    __tablename__ = "seats"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    seat_number: Mapped[int] = mapped_column(
        Integer,
        unique=True,
        nullable=False,
    )

    reservations: Mapped[list["Reservation"]] = relationship(
        back_populates="seat",
    )


class Reservation(Base):

    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
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
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    held_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped["User"] = relationship(
        back_populates="reservations",
    )

    seat: Mapped["Seat"] = relationship(
        back_populates="reservations",
    )

    activity_logs: Mapped[list["ActivityLog"]] = relationship(
        back_populates="reservation",
    )


class WaitlistEntry(Base):

    __tablename__ = "waitlist_entries"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    status: Mapped[WaitlistStatus] = mapped_column(
        nullable=False,
        default=WaitlistStatus.WAITING,
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
    )


class ActivityLog(Base):

    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    reservation_id: Mapped[int] = mapped_column(
        ForeignKey("reservations.id"),
        nullable=False,
        index=True,
    )

    previous_state: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    new_state: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    reservation: Mapped["Reservation"] = relationship(
        back_populates="activity_logs",
    )


class IdempotencyKey(Base):

    __tablename__ = "idempotency_keys"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
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
        Integer,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "key",
            "user_id",
            "operation",
            name="uq_idempotency_key_user_operation",
        ),
    )