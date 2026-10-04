from datetime import datetime

from pydantic import BaseModel, Field

from .models import ReservationStatus, WaitlistStatus


class UserResponse(BaseModel):

    id: int
    name: str
    email: str


class SeatResponse(BaseModel):

    id: int
    seat_number: int

    class Config:
        from_attributes = True


class HoldSeatRequest(BaseModel):

    seat_id: int = Field(
        gt=0,
        description="ID of the seat the user wants to hold.",
    )

    idempotency_key: str = Field(
        min_length=1,
        max_length=255,
    )


class ConfirmReservationRequest(BaseModel):

    idempotency_key: str = Field(
        min_length=1,
        max_length=255,
    )


class CancelReservationRequest(BaseModel):

    idempotency_key: str = Field(
        min_length=1,
        max_length=255,
    )


class ReservationResponse(BaseModel):

    id: int
    user_id: int
    seat_id: int
    status: ReservationStatus

    created_at: datetime
    held_until: datetime | None
    confirmed_at: datetime | None
    cancelled_at: datetime | None

    class Config:
        from_attributes = True


class JoinWaitlistRequest(BaseModel):

    idempotency_key: str = Field(
        min_length=1,
        max_length=255,
    )


class WaitlistResponse(BaseModel):

    id: int
    user_id: int
    created_at: datetime
    status: WaitlistStatus

    position: int | None = None

    class Config:
        from_attributes = True



class ActivityResponse(BaseModel):

    id: int
    reservation_id: int

    previous_state: str | None
    new_state: str

    timestamp: datetime
    reason: str

    class Config:
        from_attributes = True



class AvailabilityResponse(BaseModel):

    available: int
    held: int
    confirmed: int



class UserReservationResponse(BaseModel):

    reservation: ReservationResponse | None
    waitlist_position: int | None