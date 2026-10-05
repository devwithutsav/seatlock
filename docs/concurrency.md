# Concurrency strategy

SeatLock uses PostgreSQL row locking and transactions rather than trusting frontend state.

For a hold, the backend locks the requesting user and requested seat before checking/creating active reservations. Requests racing for one seat therefore serialize on that seat row. Requests from the same user serialize on the user row.

The waitlist is FIFO (`created_at`, then `id`). Promotion locks the next waiting entry, candidate user, and target seat before creating a new hold.

The expiry worker uses `FOR UPDATE SKIP LOCKED` for expired holds, which prevents two concurrent workers from processing the same locked hold.

`tests/test_concurrency.py` sends 100 concurrent HTTP reservation attempts using Python's built-in `asyncio` TCP streams; it also verifies capacity, duplicate-user/seat invariants, idempotent retry, expired-hold rejection, and exactly-one FIFO promotion.
