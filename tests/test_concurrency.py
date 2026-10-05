"""
SeatLock repeatable concurrency/invariant test.

No k6 and no extra HTTP client dependency. HTTP requests use asyncio's
built-in TCP streams; DB verification uses SQLAlchemy already used by the app.

Run while the backend is running:
    SEATLOCK_TEST_RESET=1 python tests/test_concurrency.py

WARNING: SEATLOCK_TEST_RESET=1 clears reservations/waitlist/activity/idempotency
rows in the configured development database. It keeps users and the 20 seats.
"""

import asyncio
import json
import os
import ssl
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import delete, func, select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    ActivityLog,
    IdempotencyKey,
    Reservation,
    ReservationStatus,
    WaitlistEntry,
    WaitlistStatus,
)

API_BASE = os.getenv("SEATLOCK_API_BASE", "http://127.0.0.1:8000").rstrip("/")
RESET = os.getenv("SEATLOCK_TEST_RESET", "0") == "1"


class Response:
    def __init__(self, status: int, headers: dict[str, str], body: bytes):
        self.status = status
        self.headers = headers
        self.body = body

    def json(self):
        return json.loads(self.body.decode() or "null")


async def request(method: str, path: str, *, body=None, cookie=None, idem=None) -> Response:
    parsed = urlparse(API_BASE)
    host = parsed.hostname or "127.0.0.1"
    secure = parsed.scheme == "https"
    port = parsed.port or (443 if secure else 80)
    ssl_context = ssl.create_default_context() if secure else None

    reader, writer = await asyncio.open_connection(host, port, ssl=ssl_context, server_hostname=host if secure else None)

    payload = b"" if body is None else json.dumps(body).encode()
    headers = {
        "Host": parsed.netloc,
        "Accept": "application/json",
        "Connection": "close",
    }
    if payload:
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(payload))
    if cookie:
        headers["Cookie"] = f"session_token={cookie}"
    if idem:
        headers["Idempotency-Key"] = idem

    target = f"{parsed.path.rstrip('/')}{path}" or "/"
    raw = f"{method} {target} HTTP/1.1\r\n" + "".join(f"{k}: {v}\r\n" for k, v in headers.items()) + "\r\n"
    writer.write(raw.encode() + payload)
    await writer.drain()

    status_line = (await reader.readline()).decode().strip()
    if not status_line:
        writer.close()
        await writer.wait_closed()
        raise RuntimeError("Backend closed the connection without a response")
    status = int(status_line.split()[1])

    response_headers: dict[str, str] = {}
    while True:
        line = await reader.readline()
        if line in (b"\r\n", b"\n", b""):
            break
        key, value = line.decode().split(":", 1)
        response_headers[key.lower()] = value.strip()

    if "content-length" in response_headers:
        response_body = await reader.readexactly(int(response_headers["content-length"]))
    else:
        response_body = await reader.read()

    writer.close()
    await writer.wait_closed()
    return Response(status, response_headers, response_body)


def cookie_from(response: Response) -> str:
    raw = response.headers.get("set-cookie", "")
    prefix = "session_token="
    start = raw.find(prefix)
    if start < 0:
        raise AssertionError("Login did not return session_token cookie")
    return raw[start + len(prefix):].split(";", 1)[0]


def check(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


async def reset_state():
    if not RESET:
        return
    async with SessionLocal() as db:
        await db.execute(delete(ActivityLog))
        await db.execute(delete(IdempotencyKey))
        await db.execute(delete(WaitlistEntry))
        await db.execute(delete(Reservation))
        await db.commit()
    print("Reset transactional test state.")


async def login_user(i: int) -> tuple[int, str]:
    response = await request(
        "POST", "/auth/login",
        body={"name": f"Load User {i}", "email": f"load-user-{i:03d}@seatlock.test"},
    )
    check(response.status == 200, f"user {i} login succeeds")
    return i, cookie_from(response)


async def database_invariants():
    async with SessionLocal() as db:
        confirmed = int(await db.scalar(select(func.count(Reservation.id)).where(Reservation.status == ReservationStatus.CONFIRMED)) or 0)

        duplicate_users = (await db.execute(
            select(Reservation.user_id, func.count(Reservation.id))
            .where(Reservation.status.in_([ReservationStatus.HELD, ReservationStatus.CONFIRMED]))
            .group_by(Reservation.user_id)
            .having(func.count(Reservation.id) > 1)
        )).all()

        duplicate_seats = (await db.execute(
            select(Reservation.seat_id, func.count(Reservation.id))
            .where(Reservation.status.in_([ReservationStatus.HELD, ReservationStatus.CONFIRMED]))
            .group_by(Reservation.seat_id)
            .having(func.count(Reservation.id) > 1)
        )).all()

    return confirmed, duplicate_users, duplicate_seats


async def main():
    print(f"Testing {API_BASE}")
    await reset_state()

    health = await request("GET", "/health")
    check(health.status == 200, "backend health endpoint is reachable")

    seats_response = await request("GET", "/seats")
    check(seats_response.status == 200, "seat list is available")
    seats = seats_response.json()
    check(len(seats) == 20, "exactly 20 seats exist")

    availability = (await request("GET", "/availability")).json()
    check(availability["available"] == 20, "test begins with 20 available seats (use SEATLOCK_TEST_RESET=1 if needed)")

    # 100 concurrent identities.
    users = dict(await asyncio.gather(*(login_user(i) for i in range(1, 101))))
    seat_ids = [seat["id"] for seat in seats]

    async def attempt_hold(i: int):
        seat_id = seat_ids[(i - 1) % 20]
        idem = f"concurrent-hold-{i}"
        response = await request("POST", "/reservations/hold", body={"seat_id": seat_id}, cookie=users[i], idem=idem)
        return i, seat_id, idem, response

    # This is the required >=100 simultaneous reservation attempt burst.
    attempts = await asyncio.gather(*(attempt_hold(i) for i in range(1, 101)))
    successes = [(i, seat_id, idem, r) for i, seat_id, idem, r in attempts if r.status == 200]
    check(len(successes) <= 20, "100 simultaneous attempts never create more than 20 holds")
    check(len(successes) == 20, "on an empty test state, all 20 seats are claimed exactly once")

    async def confirm_success(item):
        i, _, _, response = item
        reservation_id = response.json()["id"]
        result = await request("POST", f"/reservations/{reservation_id}/confirm", cookie=users[i], idem=f"confirm-{i}")
        return i, reservation_id, result

    confirmations = await asyncio.gather(*(confirm_success(item) for item in successes))
    check(all(r.status == 200 for _, _, r in confirmations), "all successful holds can be confirmed before expiry")

    confirmed, duplicate_users, duplicate_seats = await database_invariants()
    check(confirmed <= 20, "database contains no more than 20 confirmed reservations")
    check(not duplicate_users, "no user has more than one active reservation")
    check(not duplicate_seats, "no seat has more than one active reservation")

    # Idempotent retry must return the original reservation, not create another.
    first_i, first_seat, first_idem, first_response = successes[0]
    first_id = first_response.json()["id"]
    retry = await request("POST", "/reservations/hold", body={"seat_id": first_seat}, cookie=users[first_i], idem=first_idem)
    check(retry.status == 200 and retry.json()["id"] == first_id, "retrying the same idempotency key returns the same reservation")

    # Full workshop -> two FIFO waitlist entries.
    _, wait1_cookie = await login_user(101)
    _, wait2_cookie = await login_user(102)
    wait1 = await request("POST", "/waitlist/join", cookie=wait1_cookie, idem="wait-101")
    wait2 = await request("POST", "/waitlist/join", cookie=wait2_cookie, idem="wait-102")
    check(wait1.status == 200 and wait2.status == 200, "two users can join the FIFO waitlist when full")

    # Cancel one confirmed reservation: exactly the first waitlisted user is promoted.
    owner_i, reservation_id, _ = confirmations[0]
    cancelled = await request("POST", f"/reservations/{reservation_id}/cancel", cookie=users[owner_i], idem="cancel-for-promotion")
    check(cancelled.status == 200, "confirmed owner can cancel")
    await asyncio.sleep(0.15)

    promoted = await request("GET", "/reservations/me", cookie=wait1_cookie)
    second_wait = await request("GET", "/waitlist/me", cookie=wait2_cookie)
    check(promoted.status == 200 and promoted.json() is not None and promoted.json()["status"] == "HELD", "cancellation promotes the first waitlisted user")
    second_data = second_wait.json()
    check(second_data["entry"] is not None and second_data["entry"]["status"] == "WAITING" and second_data["position"] == 1, "only one waitlisted user is promoted; the next remains position 1")

    # Force the promoted hold into the past, then prove it cannot confirm.
    promoted_id = promoted.json()["id"]
    async with SessionLocal() as db:
        row = await db.get(Reservation, promoted_id)
        row.held_until = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=5)
        await db.commit()

    expired_confirm = await request("POST", f"/reservations/{promoted_id}/confirm", cookie=wait1_cookie, idem="expired-confirm")
    check(expired_confirm.status == 409, "an expired hold cannot be confirmed")

    async with SessionLocal() as db:
        row = await db.get(Reservation, promoted_id)
        check(row.status != ReservationStatus.CONFIRMED, "expired reservation remains non-confirmed in PostgreSQL")

    print("\nALL SEATLOCK CONCURRENCY CHECKS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
