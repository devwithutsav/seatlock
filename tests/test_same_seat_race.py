import asyncio
import uuid

import httpx


BASE_URL = "http://localhost:8000"


async def login(client: httpx.AsyncClient, name: str, email: str):
    response = await client.post(
        f"{BASE_URL}/auth/login",
        json={
            "name": name,
            "email": email,
        },
    )

    response.raise_for_status()

    return response.json()["token"]


async def try_hold(
    client: httpx.AsyncClient,
    token: str,
    seat_id: int,
    user_name: str,
):
    response = await client.post(
        f"{BASE_URL}/reservations/hold",
        json={
            "seat_id": seat_id,
        },
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )

    print(
        user_name,
        "→",
        response.status_code,
        response.text,
    )

    return response


async def main():
    async with httpx.AsyncClient(timeout=10) as client:

        token1 = await login(
            client,
            "Race User 1",
            f"race1-{uuid.uuid4().hex[:6]}@example.com",
        )

        token2 = await login(
            client,
            "Race User 2",
            f"race2-{uuid.uuid4().hex[:6]}@example.com",
        )

        print("\nBoth users are attempting Seat 1 simultaneously...\n")

        response1, response2 = await asyncio.gather(
            try_hold(
                client,
                token1,
                1,
                "User 1",
            ),
            try_hold(
                client,
                token2,
                1,
                "User 2",
            ),
        )

        successes = [
            response
            for response in [response1, response2]
            if response.status_code == 200
        ]

        failures = [
            response
            for response in [response1, response2]
            if response.status_code != 200
        ]

        print("\n--- RESULT ---")

        print(
            "Successful holds:",
            len(successes),
        )

        print(
            "Rejected holds:",
            len(failures),
        )

        assert len(successes) == 1
        assert len(failures) == 1

        print(
            "\nPASS: exactly one user obtained the seat."
        )


asyncio.run(main())