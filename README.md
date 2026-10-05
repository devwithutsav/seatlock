# SeatLock

Real-time, concurrency-safe reservation system for a 20-seat campus workshop.

## Stack

- Frontend: React + TypeScript + Vite
- Backend: FastAPI + async SQLAlchemy
- Database: PostgreSQL
- Real-time: WebSockets
- Concurrency test: Python `asyncio` + existing SQLAlchemy (no k6)

## Project structure

```text
seatlock/
├── backend/
│   ├── app/
│   ├── requirements.txt
│   ├── .env.example
│   ├── Dockerfile
│   └── test_db.py
├── frontend/
│   ├── src/
│   ├── package.json
│   ├── .env.example
│   ├── vercel.json
│   └── netlify.toml
├── tests/
│   └── test_concurrency.py
└── docs/
```

## 1. Local backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit DATABASE_URL in .env
python test_db.py
uvicorn app.main:app --reload
```

API docs: `http://127.0.0.1:8000/docs`

## 2. Local frontend

In another terminal:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open `http://localhost:5173`.

## 3. Concurrency test (no k6)

Keep the backend running. From the repository root, with the backend virtualenv active:

```bash
SEATLOCK_TEST_RESET=1 python tests/test_concurrency.py
```

`SEATLOCK_TEST_RESET=1` clears reservation/waitlist/activity/idempotency rows in the configured development DB so the test is repeatable. It leaves users and seats intact.

The script verifies 100 concurrent attempts, <=20 confirmed reservations, no duplicate active reservation per user/seat, idempotent retry behavior, expired-hold rejection, and exactly-one FIFO promotion.

## Deployment

Use Vercel or Netlify for `frontend/`, and a long-running Python host such as Render/Railway for `backend/`. See `docs/deployment.md`.

## Important local/production cookie setting

Local:

```text
COOKIE_SECURE=false
COOKIE_SAMESITE=lax
```

Separate HTTPS frontend/backend domains:

```text
COOKIE_SECURE=true
COOKIE_SAMESITE=none
```
