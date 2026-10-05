# SeatLock Submission Notes

## Core implementation

SeatLock implements a 20-seat reservation system with:
- temporary holds
- confirmation and cancellation
- FIFO waitlisting
- server-side ownership checks
- idempotency
- append-only activity history
- PostgreSQL row locking and database constraints
- automatic expiry recovery
- WebSocket-driven live refresh

## Concurrency model

State-changing operations use PostgreSQL transactions and row-level locking. Seat and user rows are locked during hold creation, and reservation rows are locked during confirmation/cancellation. Partial unique indexes prevent more than one active reservation for the same user or seat.

## Idempotency

Each state-changing request carries an `Idempotency-Key`. Keys are scoped by user and operation and persisted in PostgreSQL.

## Real-time behavior

After a transaction commits, the backend broadcasts a WebSocket event. Connected frontends refetch state from REST so the database remains the source of truth.

## Concurrency test

Run:

```bash
python tests/test_concurrency.py
```

Paste the actual test output below after running it locally:

```text
[PASTE ACTUAL OUTPUT HERE]
```

Do not replace this placeholder with fabricated results.
