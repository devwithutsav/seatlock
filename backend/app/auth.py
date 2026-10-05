import secrets
from datetime import timedelta

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import get_db
from .models import AuthSession, User, utc_now


# Passwordless login / upsert: provisions or updates user and returns a time-bound bearer token.
async def login_user(name: str, email: str, db: AsyncSession) -> tuple[User, str]:
    normalized_email = email.strip().lower()

    result = await db.execute(select(User).where(User.email == normalized_email))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(name=name.strip(), email=normalized_email)
        db.add(user)
        await db.flush()
    else:
        user.name = name.strip()

    # Issue a high-entropy opaque session token stored in PostgreSQL
    token = secrets.token_urlsafe(48)
    session = AuthSession(
        token=token,
        user_id=user.id,
        expires_at=utc_now() + timedelta(days=settings.SESSION_DAYS),
    )
    db.add(session)
    await db.commit()
    await db.refresh(user)
    return user, token


# FastAPI dependency: resolves User from Bearer token and enforces session TTL.
async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    result = await db.execute(
        select(AuthSession, User)
        .join(User, User.id == AuthSession.user_id)
        .where(AuthSession.token == token)
    )
    row = result.first()

    if row is None:
        raise HTTPException(status_code=401, detail="Invalid session")

    session, user = row

    # Lazy-delete expired sessions on access
    if session.expires_at <= utc_now():
        await db.delete(session)
        await db.commit()
        raise HTTPException(status_code=401, detail="Session expired")

    return user


# Invalidates token on user sign-out
async def logout_user(token: str, db: AsyncSession) -> None:
    result = await db.execute(select(AuthSession).where(AuthSession.token == token))
    session = result.scalar_one_or_none()
    if session is not None:
        await db.delete(session)
        await db.commit()


# Non-throwing user resolution for WebSocket authentication query params
async def user_from_token(token: str, db: AsyncSession) -> User | None:
    result = await db.execute(
        select(AuthSession, User)
        .join(User, User.id == AuthSession.user_id)
        .where(AuthSession.token == token)
    )
    row = result.first()
    if row is None:
        return None
    session, user = row
    if session.expires_at <= utc_now():
        return None
    return user