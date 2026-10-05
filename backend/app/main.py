from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import Base, engine

from . import models


@asynccontextmanager
async def lifespan(app: FastAPI):

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    await engine.dispose()


app = FastAPI(
    title="SeatLock",
    description="Real-time reservation system",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    return {
        "message": "SeatLock API is running"
    }