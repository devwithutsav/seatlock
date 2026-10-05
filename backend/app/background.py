import asyncio

from .database import SessionLocal


async def expire_holds():

    while True:

        try:
            async with SessionLocal() as db:

                pass

        except Exception as exc:
            print(
                f"Background expiry worker error: {exc}"
            )

        await asyncio.sleep(5)