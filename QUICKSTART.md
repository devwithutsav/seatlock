# SeatLock — complete setup

## 1. Use a fresh PostgreSQL database

The rebuilt project uses timezone-aware PostgreSQL timestamps and new constraints. Basically a 5-minute session is considered but due to time-zone issue, session keeps getting expired ASAP when booked a seat.

```bash
createdb seatlock_rebuilt
```

Create `backend/.env`:

```env
DATABASE_URL=postgresql+asyncpg://utsavkhandelwal:********@localhost:5432/seatlock_rebuilt
FRONTEND_ORIGINS=http://localhost:5173
HOLD_DURATION_SECONDS=300
SESSION_DAYS=7
```

## 2. Start backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host localhost --port 8000
```

Check `http://localhost:8000/health`.

## 3. Start frontend

```bash
cd frontend
npm install
npm run build
npm run dev
```

Open `http://localhost:5173`.

## 4. Push to GitHub

Do not commit `backend/.env`.

```bash
git add .
git commit -m "Rebuild SeatLock full-stack reservation system"
git push
```