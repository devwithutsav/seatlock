# Deployment

## Frontend: Vercel or Netlify

Deploy the `frontend/` directory as a Vite project.

Set:

```text
VITE_API_BASE_URL=https://YOUR-BACKEND-DOMAIN
```

The repository includes `frontend/vercel.json` and `frontend/netlify.toml`.

## Backend: Render / Railway / another long-running Python host

SeatLock needs a continuously running FastAPI process for WebSockets and the expiry loop, so deploy `backend/` on a long-running Python service rather than treating it as a static frontend deployment.

Start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Required backend environment variables:

```text
DATABASE_URL=postgresql+asyncpg://...
FRONTEND_ORIGINS=https://YOUR-FRONTEND.vercel.app
COOKIE_SECURE=true
COOKIE_SAMESITE=none
```

For this recruitment-grade in-memory session implementation, run **one backend worker/process**. A backend restart logs users out, but reservation/hold state itself remains in PostgreSQL and expired holds are recovered by the expiry worker.
