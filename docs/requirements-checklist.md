# Requirements checklist

- [x] 20-seat workshop
- [x] available / held / confirmed counts
- [x] temporary hold with expiry
- [x] server-validated identity
- [x] owner-only confirm/cancel
- [x] no confirm after expiry
- [x] one active reservation per user via transactional locking
- [x] FIFO waitlist and duplicate prevention
- [x] exactly-one promotion logic
- [x] PostgreSQL persistence
- [x] transactions / row locking
- [x] idempotency key on every state-changing endpoint
- [x] append-only activity timeline
- [x] restart recovery through persisted `held_until`
- [x] WebSocket live updates
- [x] repeatable 100-concurrent-attempt Python test; no k6
- [x] frontend deployable on Vercel/Netlify
