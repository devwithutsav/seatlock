# Architecture

```text
Browser (React + TypeScript + Vite)
        |
        | REST + HttpOnly session cookie
        | WebSocket live events
        v
FastAPI / Uvicorn
        |
        | Async SQLAlchemy transactions + row locks
        v
PostgreSQL

FastAPI lifespan
        └── expiry worker -> expires overdue holds -> FIFO promotion -> WebSocket broadcast
```

The frontend never decides capacity or ownership. Reservation correctness lives in PostgreSQL-backed backend transactions.
