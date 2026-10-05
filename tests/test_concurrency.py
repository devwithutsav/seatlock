import asyncio
import os
import uuid

import httpx


BASE = os.environ.get("SEATLOCK_BASE_URL", "http://localhost:8000").rstrip("/")


async def login(client: httpx.AsyncClient, i: int):
    response = await client.post(
        f"{BASE}/auth/login",
        json={"name": f"User {i}", "email": f"user{i}-{uuid.uuid4().hex[:8]}@example.com"},
    )
    response.raise_for_status()
    return response.json()["token"]


def headers(token: str, prefix: str):
    return {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": f"{prefix}-{uuid.uuid4()}",
    }


async def main():
    async with httpx.AsyncClient(timeout=20.0) as client:
        tokens = await asyncio.gather(*(login(client, i) for i in range(100)))

        async def attempt(i: int):
            seat_id = (i % 20) + 1
            response = await client.post(
                f"{BASE}/reservations/hold",
                json={"seat_id": seat_id},
                headers=headers(tokens[i], "hold"),
            )
            return i, response

        attempts = await asyncio.gather(*(attempt(i) for i in range(100)))
        held = [(i, r.json()) for i, r in attempts if r.status_code == 200]

        assert len(held) <= 20, f"Too many holds: {len(held)}"

        confirmed = []
        for i, reservation in held:
            response = await client.post(
                f"{BASE}/reservations/{reservation['id']}/confirm",
                headers=headers(tokens[i], "confirm"),
            )
            if response.status_code == 200:
                confirmed.append(response.json())

        assert len(confirmed) <= 20, f"Too many confirmed: {len(confirmed)}"
        assert len({r["user_id"] for r in confirmed}) == len(confirmed), "A user has >1 active reservation"
        assert len({r["seat_id"] for r in confirmed}) == len(confirmed), "A seat was double-booked"

        availability = (await client.get(f"{BASE}/availability")).json()
        assert availability["confirmed"] <= 20

        print(f"100 simultaneous attempts: PASS")
        print(f"Confirmed reservations: {availability['confirmed']}")
        print("No duplicate active user reservations: PASS")
        print("No double-booked seats: PASS")

        print("\nNote: expiry/waitlist checks are easiest with HOLD_DURATION_SECONDS=2 on a test backend.")


asyncio.run(main())
