from contextlib import asynccontextmanager

from fastapi import (
    Cookie,
    Depends,
    FastAPI,
    Response,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select

from .database import Base, engine, get_db
from . import models
from .auth import (
    get_current_user,
    login_user,
    logout_user,
)
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

from .background import expire_holds



class LoginRequest(BaseModel):
    name: str
    email: str


async def initialize_database():
    """
    Create database tables and seed the 20 workshop seats.
    """

    async with engine.begin() as conn:

        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine) as db:

        result = await db.execute(
            select(models.Seat)
        )

        existing_seats = result.scalars().all()

        existing_numbers = {
            seat.seat_number
            for seat in existing_seats
        }

        for seat_number in range(1, 21):

            if seat_number not in existing_numbers:
                db.add(
                    models.Seat(
                        seat_number=seat_number
                    )
                )

        await db.commit()



@asynccontextmanager
async def lifespan(app: FastAPI):

    print("Initializing database...")

    await initialize_database()

    print("Database initialized.")

    # Start background expiry worker.
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

        print("Shutting down database connection...")

        await engine.dispose()



app = FastAPI(
    title="SeatLock",
    description="Real-time workshop seat reservation system",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.get("/")
async def root():
    return {
        "message": "SeatLock API is running"
    }


@app.post("/auth/login")
async def login(
    request: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Log in a user.

    For this project, providing a name and email is enough to establish
    a demo identity.
    """

    user = await login_user(
        email=request.email,
        name=request.name,
        response=response,
        db=db,
    )

    return {
        "message": "Login successful",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
        },
    }


@app.get("/auth/me")
async def get_me(
    current_user: models.User = Depends(get_current_user),
):
    """
    Return the currently authenticated user.

    This endpoint is useful for testing whether the session cookie works.
    """

    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
    }


@app.post("/auth/logout")
async def logout(
    response: Response,
    session_token: str | None = Cookie(default=None),
):
    """
    Log the current user out.
    """

    await logout_user(
        session_token=session_token,
        response=response,
    )

    return {
        "message": "Logout successful"
    }