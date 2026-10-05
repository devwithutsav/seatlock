# Task ID: SeatLock

SeatLock is a real-time reservation system for a small campus workshop with only 20 seats. The application looks simple from the outside — choose a seat, hold it, confirm it, or join a waitlist — but the interesting part is what happens when many people try to do those things simultaneously

The goal of the project is to make the reservation state trustworthy. A seat should never be confirmed by two users, an expired hold should never be confirmable, retrying the same request should not create duplicate side effects, and a waitlisted user should be promoted in FIFO order when a seat becomes free.

## What the app supports

- Live counts for available, held, and confirmed seats
- A visual 20-seat grid
- Five-minute temporary holds
- Confirming and cancelling reservations
- One active reservation per user
- FIFO waitlist with automatic promotion
- Real-time updates over WebSockets, with periodic polling as a fallback
- Idempotency keys on every state-changing request
- Append-only reservation activity history
- PostgreSQL-backed state so holds survive server restarts
- A concurrency test that can fire 100 simultaneous reservation attempts

## Tech stack

The frontend is React + TypeScript + Vite. The backend is FastAPI with async SQLAlchemy and asyncpg. PostgreSQL stores the durable state, and WebSockets are used to tell connected browsers that something changed so they can refresh immediately.

```text
Browser / React
      |
      | REST + Bearer session
      v
FastAPI
      |
      | async SQLAlchemy
      v
PostgreSQL

FastAPI ---- WebSocket ----> connected browsers
```

## How the reservation logic works

A reservation moves through a small state machine:

```text
AVAILABLE seat
      |
      | hold
      v
    HELD
   /    \
confirm  timeout/cancel
  |        |
  v        v
CONFIRMED  EXPIRED/CANCELLED
    |
    | cancel
    v
CANCELLED
```

A `HELD` reservation has a `held_until` timestamp. The server — not the browser — decides whether the hold is still valid. The frontend countdown is only a display. On confirm, FastAPI locks the reservation row and checks `held_until` against the current UTC time before allowing the transition to `CONFIRMED`.

All timestamps are stored as timezone-aware PostgreSQL timestamps and created in UTC. This avoids the local-time/UTC ambiguity that can make a fresh hold look expired in the browser.

## What happens under the hood

### 1. Holding a seat

When a user clicks an available seat:

1. The frontend generates a unique `Idempotency-Key`.
2. FastAPI validates the user session.
3. The backend claims the idempotency key.
4. The user row is locked so two requests for the same user cannot create two active reservations.
5. The requested seat row is locked so concurrent requests for that seat are serialized.
6. The backend checks that neither the user nor the seat already has an active reservation.
7. A `HELD` reservation is created with `held_until = now + 5 minutes`.
8. An append-only activity row is written.
9. The transaction commits.
10. A WebSocket event tells connected clients that reservation state changed.

PostgreSQL also has partial unique indexes for active reservations. The application locks are the first line of concurrency control, while the database constraints are a final safety net.

### 2. Confirming a hold

Confirmation is always checked on the server.

The backend locks the reservation, verifies ownership, verifies that its state is still `HELD`, and compares its UTC `held_until` value with the server clock. Only then does it transition the reservation to `CONFIRMED`.

An expired hold is changed to `EXPIRED` and cannot be confirmed.

### 3. Expiry and restart recovery

A background coroutine scans for expired holds. It uses `FOR UPDATE SKIP LOCKED`, allowing work to be divided safely if rows are already involved in another transaction.

Expiry is not based on an in-memory timer. The deadline is stored in PostgreSQL. On backend startup, SeatLock runs an expiry pass before serving normal traffic, which means stale holds can be recovered after a restart.

### 4. Waitlist promotion

The waitlist is ordered by `created_at` and then `id`, giving deterministic FIFO ordering.

When a hold expires or a reservation is cancelled, the backend locks the oldest waiting entry and promotes exactly one eligible user to a new temporary hold on the freed seat. That promotion happens inside the same database transaction as the release of the seat.

### 5. Idempotency

Every state-changing endpoint requires an `Idempotency-Key`.

The key is stored together with the user and operation. Once the request succeeds, it is linked to the affected resource. If the same request is retried — for example because the browser did not receive the original response — the backend returns the original result instead of creating a second reservation.

### 6. Real-time updates

The backend broadcasts small WebSocket events after successful commits. Browsers do not trust those event payloads as database state; they use the event as a signal to refetch the authoritative seat and reservation state over REST.

A 10-second polling fallback is also enabled so the UI can recover if a WebSocket connection drops.

## Local setup

### PostgreSQL

Create a **fresh database**. Do not point this rebuilt version at the old SeatLock database because `create_all()` does not migrate existing column types or constraints:

```bash
createdb seatlock_rebuilt
```

Create `backend/.env` from the example:

```bash
cd backend
cp .env.example .env
```

Set your own PostgreSQL URL:

```env
DATABASE_URL=postgresql+asyncpg://utsavkhandelwal:********@localhost:5432/seatlock_rebuilt
FRONTEND_ORIGINS=http://localhost:5173
HOLD_DURATION_SECONDS=300
SESSION_DAYS=7
```

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host localhost --port 8000
```

Check:

```text
http://localhost:8000/health
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

During local development Vite proxies `/api` to the FastAPI backend, so no frontend `.env` is required.


## Concurrency test

Install the test dependencies:

```bash
pip install -r tests/requirements.txt
```

Against a clean local database:

```bash
export DATABASE_URL='postgresql+asyncpg://utsavkhandelwal:********@localhost:5432/seatlock_rebuilt'
export ALLOW_TEST_RESET=true
python tests/reset_db.py
python tests/test_concurrency.py
```

The script launches 100 reservation attempts concurrently and checks the key capacity invariants.

## Repository structure

```text
seatlock/
├── backend/
│   ├── app/
│   │   ├── auth.py
│   │   ├── background.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── idempotency.py
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── realtime.py
│   │   ├── reservations.py
│   │   ├── schemas.py
│   │   └── waitlist.py
│   ├── .env.example
│   ├── Dockerfile
│   ├── render.yaml
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── api.ts
│   │   ├── App.tsx
│   │   ├── auth.ts
│   │   ├── date.ts
│   │   ├── main.tsx
│   │   ├── styles.css
│   │   └── types.ts
│   ├── .env.example
│   ├── package.json
│   ├── tsconfig.json
│   ├── vercel.json
│   └── vite.config.ts
├── tests/
│   ├── reset_db.py
│   ├── requirements.txt
│   └── test_concurrency.py
├── docker-compose.yml
├── .gitignore
└── README.md
```

## Notes

This project intentionally keeps the system small enough to understand while still making the correctness problems explicit. The interesting part of SeatLock is not rendering twenty buttons; it is making sure those twenty buttons remain truthful when many users are clicking at the same time.
