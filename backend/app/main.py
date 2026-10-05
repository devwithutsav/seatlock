"""
SeatLock FastAPI application.
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import (
    Cookie,
    Depends,
    FastAPI,
    Header,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from . import models
from .auth import (
    get_current_user,
    login_user,
    logout_user,
)
from .background import expire_holds
from .database import (
    Base,
    SessionLocal,
    engine,
    get_db,
    settings,
)
from .reservations import (
    cancel_reservation,
    confirm_reservation,
    get_active_reservation_for_user,
    hold_seat,
)
from .realtime import manager
from .schemas import (
    ActivityResponse,
    AvailabilityResponse,
    HoldSeatRequest,
    LoginRequest,
    ReservationResponse,
    SeatStateResponse,
    UserResponse,
    WaitlistResponse,
    WaitlistStatusResponse,
)
from .waitlist import (
    cancel_waitlist,
    get_active_waitlist_entry,
    get_waitlist_position,
    join_waitlist,
)


# ---------------------------------------------------------------------------
# Database initialization
# ---------------------------------------------------------------------------

async def initialize_database():
    """
    Create all tables and ensure seats 1-20 exist.
    """

    async with engine.begin() as conn:

        await conn.run_sync(
            Base.metadata.create_all
        )


    async with SessionLocal() as db:

        result = await db.execute(
            select(models.Seat)
        )

        seats = result.scalars().all()

        existing_numbers = {
            seat.seat_number
            for seat in seats
        }

        for seat_number in range(1, 21):

            if seat_number not in existing_numbers:

                db.add(
                    models.Seat(
                        seat_number=seat_number
                    )
                )

        await db.commit()


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):

    print("Initializing SeatLock database...")

    await initialize_database()

    print("Database ready.")

    expiry_task = asyncio.create_task(
        expire_holds()
    )

    try:

        yield

    finally:

        expiry_task.cancel()

        try:
            await expiry_task
        except asyncio.CancelledError:
            pass

        await engine.dispose()

        print("SeatLock shutdown complete.")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SeatLock",
    description="Real-time reservation system for a 20-seat workshop",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return {
        "message": "SeatLock API is running"
    }


@app.get("/health")
async def health():
    return {
        "status": "ok"
    }


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

@app.post(
    "/auth/login",
    response_model=UserResponse,
)
async def login(
    request: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    user = await login_user(
        email=request.email,
        name=request.name,
        response=response,
        db=db,
    )

    return user


@app.get(
    "/auth/me",
    response_model=UserResponse,
)
async def me(
    current_user: models.User = Depends(
        get_current_user
    ),
):
    return current_user


@app.post("/auth/logout")
async def logout(
    response: Response,
    session_token: str | None = Cookie(
        default=None
    ),
):
    logout_user(
        session_token,
        response,
    )

    return {
        "message": "Logout successful"
    }


# ---------------------------------------------------------------------------
# Seats
# ---------------------------------------------------------------------------

@app.get(
    "/seats",
    response_model=list[SeatStateResponse],
)
async def get_seats(
    db: AsyncSession = Depends(get_db),
):
    seats_result = await db.execute(
        select(models.Seat)
        .order_by(models.Seat.seat_number)
    )

    seats = seats_result.scalars().all()


    reservations_result = await db.execute(
        select(models.Reservation)
        .where(
            models.Reservation.status.in_(
                [
                    models.ReservationStatus.HELD,
                    models.ReservationStatus.CONFIRMED,
                ]
            )
        )
    )

    reservations = (
        reservations_result.scalars().all()
    )


    reservation_by_seat = {
        reservation.seat_id: reservation
        for reservation in reservations
    }


    response = []

    for seat in seats:

        reservation = reservation_by_seat.get(
            seat.id
        )

        if reservation is None:

            seat_status = "AVAILABLE"

        else:

            seat_status = (
                reservation.status.value
            )


        response.append(
            {
                "id": seat.id,
                "seat_number": seat.seat_number,
                "status": seat_status,
                "reservation_id": (
                    reservation.id
                    if reservation
                    else None
                ),
                "held_until": (
                    reservation.held_until
                    if reservation
                    and reservation.status
                    == models.ReservationStatus.HELD
                    else None
                ),
            }
        )

    return response


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------

@app.get(
    "/availability",
    response_model=AvailabilityResponse,
)
async def availability(
    db: AsyncSession = Depends(get_db),
):

    total = (
        await db.scalar(
            select(func.count(models.Seat.id))
        )
    )


    held = (
        await db.scalar(
            select(
                func.count(
                    models.Reservation.id
                )
            ).where(
                models.Reservation.status
                == models.ReservationStatus.HELD
            )
        )
    )


    confirmed = (
        await db.scalar(
            select(
                func.count(
                    models.Reservation.id
                )
            ).where(
                models.Reservation.status
                == models.ReservationStatus.CONFIRMED
            )
        )
    )


    total = int(total or 0)
    held = int(held or 0)
    confirmed = int(confirmed or 0)

    available = (
        total
        - held
        - confirmed
    )


    return {
        "total": total,
        "available": available,
        "held": held,
        "confirmed": confirmed,
    }


# ---------------------------------------------------------------------------
# Reservation: hold
# ---------------------------------------------------------------------------

@app.post(
    "/reservations/hold",
    response_model=ReservationResponse,
)
async def create_hold(
    request: HoldSeatRequest,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=1,
    ),
    current_user: models.User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
):

    return await hold_seat(
        db=db,
        user=current_user,
        seat_id=request.seat_id,
        idempotency_key=idempotency_key,
    )


# ---------------------------------------------------------------------------
# Reservation: confirm
# ---------------------------------------------------------------------------

@app.post(
    "/reservations/{reservation_id}/confirm",
    response_model=ReservationResponse,
)
async def confirm(
    reservation_id: int,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=1,
    ),
    current_user: models.User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
):

    return await confirm_reservation(
        db=db,
        user=current_user,
        reservation_id=reservation_id,
        idempotency_key=idempotency_key,
    )


# ---------------------------------------------------------------------------
# Reservation: cancel
# ---------------------------------------------------------------------------

@app.post(
    "/reservations/{reservation_id}/cancel",
    response_model=ReservationResponse,
)
async def cancel(
    reservation_id: int,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=1,
    ),
    current_user: models.User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
):

    return await cancel_reservation(
        db=db,
        user=current_user,
        reservation_id=reservation_id,
        idempotency_key=idempotency_key,
    )


# ---------------------------------------------------------------------------
# Current user's reservation
# ---------------------------------------------------------------------------

@app.get(
    "/reservations/me",
    response_model=ReservationResponse | None,
)
async def my_reservation(
    current_user: models.User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
):

    return await get_active_reservation_for_user(
        db,
        current_user.id,
    )


# ---------------------------------------------------------------------------
# Activity timeline
# ---------------------------------------------------------------------------

@app.get(
    "/reservations/{reservation_id}/activity",
    response_model=list[ActivityResponse],
)
async def reservation_activity(
    reservation_id: int,
    current_user: models.User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
):

    reservation_result = await db.execute(
        select(models.Reservation)
        .where(
            models.Reservation.id
            == reservation_id,
            models.Reservation.user_id
            == current_user.id,
        )
    )

    reservation = (
        reservation_result.scalar_one_or_none()
    )

    if reservation is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail="Reservation not found",
        )


    result = await db.execute(
        select(models.ActivityLog)
        .where(
            models.ActivityLog.reservation_id
            == reservation_id
        )
        .order_by(
            models.ActivityLog.timestamp,
            models.ActivityLog.id,
        )
    )

    return result.scalars().all()


# ---------------------------------------------------------------------------
# Waitlist: join
# ---------------------------------------------------------------------------

@app.post(
    "/waitlist/join",
    response_model=WaitlistResponse,
)
async def waitlist_join(
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=1,
    ),
    current_user: models.User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
):

    return await join_waitlist(
        db=db,
        user=current_user,
        idempotency_key=idempotency_key,
    )


# ---------------------------------------------------------------------------
# Waitlist: cancel
# ---------------------------------------------------------------------------

@app.post(
    "/waitlist/{entry_id}/cancel",
    response_model=WaitlistResponse,
)
async def waitlist_cancel(
    entry_id: int,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=1,
    ),
    current_user: models.User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
):

    return await cancel_waitlist(
        db=db,
        user=current_user,
        entry_id=entry_id,
        idempotency_key=idempotency_key,
    )


# ---------------------------------------------------------------------------
# Current user's waitlist position
# ---------------------------------------------------------------------------

@app.get(
    "/waitlist/me",
    response_model=WaitlistStatusResponse,
)
async def my_waitlist_status(
    current_user: models.User = Depends(
        get_current_user
    ),
    db: AsyncSession = Depends(get_db),
):

    entry = await get_active_waitlist_entry(
        db,
        current_user.id,
    )

    if entry is None:

        return {
            "entry": None,
            "position": None,
        }


    position = await get_waitlist_position(
        db,
        entry,
    )

    return {
        "entry": entry,
        "position": position,
    }


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
):

    await manager.connect(
        websocket
    )

    try:

        while True:

            await websocket.receive_text()

    except WebSocketDisconnect:

        manager.disconnect(
            websocket
        )