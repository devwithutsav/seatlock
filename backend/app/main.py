import asyncio
from contextlib import asynccontextmanager

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from . import models
from .auth import get_current_user, login_user, logout_user, user_from_token
from .background import expire_holds_once, expiry_worker
from .config import settings
from .database import Base, SessionLocal, engine, get_db
from .realtime import manager
from .reservations import (
    cancel_reservation,
    confirm_reservation,
    get_active_reservation_for_user,
    hold_seat,
)
from .schemas import (
    ActivityResponse,
    AvailabilityResponse,
    HoldSeatRequest,
    LoginRequest,
    LoginResponse,
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


async def initialize_database() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        count = await db.scalar(select(func.count(models.Seat.id)))
        if int(count or 0) == 0:
            db.add_all([models.Seat(seat_number=i) for i in range(1, 21)])
            await db.commit()

    await expire_holds_once()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await initialize_database()
    task = asyncio.create_task(expiry_worker())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await engine.dispose()


app = FastAPI(
    title="SeatLock API",
    version="1.0.0",
    description="Concurrency-safe reservation API for a 20-seat workshop.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "SeatLock API is running"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    user, token = await login_user(request.name, request.email, db)
    return {"token": token, "user": user}


@app.get("/auth/me", response_model=UserResponse)
async def me(current_user: models.User = Depends(get_current_user)):
    return current_user


@app.post("/auth/logout")
async def logout(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    if authorization and authorization.startswith("Bearer "):
        await logout_user(authorization[7:].strip(), db)
    return {"message": "Logged out"}


@app.get("/seats", response_model=list[SeatStateResponse])
async def get_seats(db: AsyncSession = Depends(get_db)):
    await expire_holds_once()

    seats_result = await db.execute(select(models.Seat).order_by(models.Seat.seat_number))
    seats = seats_result.scalars().all()

    active_result = await db.execute(
        select(models.Reservation).where(
            models.Reservation.status.in_(
                [models.ReservationStatus.HELD, models.ReservationStatus.CONFIRMED]
            )
        )
    )
    active = active_result.scalars().all()
    by_seat = {reservation.seat_id: reservation for reservation in active}

    return [
        {
            "id": seat.id,
            "seat_number": seat.seat_number,
            "status": by_seat[seat.id].status.value if seat.id in by_seat else "AVAILABLE",
            "reservation_id": by_seat[seat.id].id if seat.id in by_seat else None,
            "held_until": (
                by_seat[seat.id].held_until
                if seat.id in by_seat and by_seat[seat.id].status == models.ReservationStatus.HELD
                else None
            ),
        }
        for seat in seats
    ]


@app.get("/availability", response_model=AvailabilityResponse)
async def availability(db: AsyncSession = Depends(get_db)):
    await expire_holds_once()

    total = int(await db.scalar(select(func.count(models.Seat.id))) or 0)
    held = int(
        await db.scalar(
            select(func.count(models.Reservation.id)).where(
                models.Reservation.status == models.ReservationStatus.HELD
            )
        )
        or 0
    )
    confirmed = int(
        await db.scalar(
            select(func.count(models.Reservation.id)).where(
                models.Reservation.status == models.ReservationStatus.CONFIRMED
            )
        )
        or 0
    )

    return {
        "total": total,
        "available": total - held - confirmed,
        "held": held,
        "confirmed": confirmed,
    }


@app.post("/reservations/hold", response_model=ReservationResponse)
async def create_hold(
    request: HoldSeatRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1),
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await hold_seat(db, current_user, request.seat_id, idempotency_key)


@app.post("/reservations/{reservation_id}/confirm", response_model=ReservationResponse)
async def confirm(
    reservation_id: int,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1),
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await confirm_reservation(
        db,
        current_user,
        reservation_id,
        idempotency_key,
    )


@app.post("/reservations/{reservation_id}/cancel", response_model=ReservationResponse)
async def cancel(
    reservation_id: int,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1),
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await cancel_reservation(
        db,
        current_user,
        reservation_id,
        idempotency_key,
    )


@app.get("/reservations/me", response_model=ReservationResponse | None)
async def my_reservation(
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await expire_holds_once()
    return await get_active_reservation_for_user(db, current_user.id)


@app.get("/reservations/{reservation_id}/activity", response_model=list[ActivityResponse])
async def reservation_activity(
    reservation_id: int,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    owns = await db.scalar(
        select(func.count(models.Reservation.id)).where(
            models.Reservation.id == reservation_id,
            models.Reservation.user_id == current_user.id,
        )
    )
    if not owns:
        raise HTTPException(status_code=404, detail="Reservation not found")

    result = await db.execute(
        select(models.ActivityLog)
        .where(models.ActivityLog.reservation_id == reservation_id)
        .order_by(models.ActivityLog.timestamp, models.ActivityLog.id)
    )
    return result.scalars().all()


@app.post("/waitlist/join", response_model=WaitlistResponse)
async def waitlist_join(
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1),
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await join_waitlist(db, current_user, idempotency_key)


@app.post("/waitlist/{entry_id}/cancel", response_model=WaitlistResponse)
async def waitlist_cancel(
    entry_id: int,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1),
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await cancel_waitlist(
        db,
        current_user,
        entry_id,
        idempotency_key,
    )


@app.get("/waitlist/me", response_model=WaitlistStatusResponse)
async def my_waitlist(
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await get_active_waitlist_entry(db, current_user.id)
    if entry is None:
        return {"entry": None, "position": None}

    return {
        "entry": entry,
        "position": await get_waitlist_position(db, entry),
    }


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
):
    async with SessionLocal() as db:
        user = await user_from_token(token, db)

    if user is None:
        await websocket.close(code=1008)
        return

    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
