"""
Pydantic request/response schemas.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=255)


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class UserResponse(BaseModel):
    id: int
    name: str
    email: str

    model_config = ConfigDict(
        from_attributes=True
    )


# ---------------------------------------------------------------------------
# Reservation
# ---------------------------------------------------------------------------

class HoldSeatRequest(BaseModel):
    seat_id: int = Field(gt=0)


class ReservationResponse(BaseModel):
    id: int
    user_id: int
    seat_id: int
    status: str
    created_at: datetime
    held_until: datetime | None
    confirmed_at: datetime | None
    cancelled_at: datetime | None

    model_config = ConfigDict(
        from_attributes=True
    )


# ---------------------------------------------------------------------------
# Seat
# ---------------------------------------------------------------------------

class SeatResponse(BaseModel):
    id: int
    seat_number: int

    model_config = ConfigDict(
        from_attributes=True
    )


class SeatStateResponse(BaseModel):
    id: int
    seat_number: int
    status: str
    reservation_id: int | None
    held_until: datetime | None


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------

class AvailabilityResponse(BaseModel):
    total: int
    available: int
    held: int
    confirmed: int


# ---------------------------------------------------------------------------
# Waitlist
# ---------------------------------------------------------------------------

class WaitlistResponse(BaseModel):
    id: int
    user_id: int
    status: str
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class WaitlistStatusResponse(BaseModel):
    entry: WaitlistResponse | None
    position: int | None


# ---------------------------------------------------------------------------
# Activity
# ---------------------------------------------------------------------------

class ActivityResponse(BaseModel):
    id: int
    reservation_id: int
    previous_state: str | None
    new_state: str
    timestamp: datetime
    reason: str

    model_config = ConfigDict(
        from_attributes=True
    )