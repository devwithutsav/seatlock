# Database model

- `users`: server-validated demo identities.
- `seats`: exactly 20 seeded workshop seats.
- `reservations`: `HELD`, `CONFIRMED`, `CANCELLED`, `EXPIRED` state and timestamps.
- `waitlist_entries`: FIFO `WAITING`, `PROMOTED`, `CANCELLED` entries.
- `activity_logs`: append-only state transition history.
- `idempotency_keys`: durable `(key, user_id, operation)` retry protection.

## Timestamp convention

The existing schema uses PostgreSQL `TIMESTAMP WITHOUT TIME ZONE`. The application therefore stores **naive UTC** consistently. The frontend interprets those values as UTC before displaying them.
