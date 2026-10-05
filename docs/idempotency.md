# Idempotency strategy

Every state-changing endpoint requires `Idempotency-Key`.

The backend first attempts a PostgreSQL `INSERT ... ON CONFLICT DO NOTHING` into `idempotency_keys`, whose unique key is `(key, user_id, operation)`. The successful operation stores its resulting resource ID on that row in the same transaction.

A retry with the same key returns the original resource instead of repeating the side effect. If the transaction fails, the idempotency insert rolls back with it.
