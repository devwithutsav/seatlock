import secrets

from fastapi import Cookie, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .models import User



sessions: dict[str, int] = {}


async def login_user(
    email: str,
    name: str,
    response: Response,
    db: AsyncSession,
) -> User:
   
    result = await db.execute(
        select(User).where(User.email == email)
    )

    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            name=name,
            email=email,
        )

        db.add(user)
        await db.flush()

    session_token = secrets.token_urlsafe(32)

    sessions[session_token] = user.id

    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        samesite="lax",
        secure=False,
    )

    await db.commit()

    return user


async def get_current_user(
    session_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:

    if session_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    user_id = sessions.get(session_token)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    result = await db.execute(
        select(User).where(User.id == user_id)
    )

    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
        )

    return user


async def logout_user(
    session_token: str | None,
    response: Response,
):
    

    if session_token is not None:
        sessions.pop(session_token, None)

    response.delete_cookie(
        key="session_token"
    )