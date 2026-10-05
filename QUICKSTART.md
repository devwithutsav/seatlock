# SeatLock — 30 minute setup

## 1. Use a fresh PostgreSQL database

The rebuilt project uses timezone-aware PostgreSQL timestamps and new constraints. Do not reuse the old SeatLock schema.

```bash
createdb seatlock_rebuilt
```

Create `backend/.env`:

```env
DATABASE_URL=postgresql+asyncpg://YOUR_POSTGRES_USER:YOUR_PASSWORD@localhost:5432/seatlock_rebuilt
FRONTEND_ORIGINS=http://localhost:5173
HOLD_DURATION_SECONDS=300
SESSION_DAYS=7
```

If local Postgres does not require a password:

```env
DATABASE_URL=postgresql+asyncpg://YOUR_POSTGRES_USER@localhost:5432/seatlock_rebuilt
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

## 5. Deploy backend first

Use Render or Railway because the backend needs a continuously running FastAPI process and WebSockets.

Backend environment variables:

```env
DATABASE_URL=<managed PostgreSQL URL>
FRONTEND_ORIGINS=https://YOUR-VERCEL-APP.vercel.app
HOLD_DURATION_SECONDS=300
SESSION_DAYS=7
```

Start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## 6. Deploy frontend to Vercel

Import the same GitHub repository and set:

- Root Directory: `frontend`
- Framework: Vite
- Build command: `npm run build`
- Output directory: `dist`

Environment variable:

```env
VITE_API_BASE_URL=https://YOUR-BACKEND-DOMAIN
```

Redeploy after setting it.

## Important

The FastAPI backend itself should not be deployed as a Vercel serverless function for this assignment because SeatLock depends on a persistent expiry worker and WebSocket connections. Vercel is used for the React frontend; Render/Railway hosts the backend.
