import asyncio
import os

import asyncpg


async def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("Set DATABASE_URL first.")

    if os.environ.get("ALLOW_TEST_RESET") != "true":
        raise SystemExit("Refusing to reset. Set ALLOW_TEST_RESET=true.")

    url = url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(url)
    try:
        await conn.execute("""
            TRUNCATE TABLE
                activity_logs,
                idempotency_keys,
                waitlist_entries,
                reservations,
                auth_sessions,
                users,
                seats
            RESTART IDENTITY CASCADE;
        """)
        await conn.executemany(
            "INSERT INTO seats (seat_number) VALUES ($1)",
            [(i,) for i in range(1, 21)],
        )
        print("Database reset complete.")
    finally:
        await conn.close()


asyncio.run(main())
