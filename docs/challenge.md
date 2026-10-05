## Task ID: SeatLock

#### `Full Stack Web Development`, `Databases`, `Concurrency`, `Real-Time Systems`

Mentors: [Sourabh Kapure](https://github.com/Spkap) ([+91 7021991449](https://wa.me/917021991449))

Difficulty: `Medium-Hard`

### Description

Build **SeatLock**, a real-time reservation system for a campus workshop with only **20 seats**. Users should be able to hold a seat temporarily, confirm or cancel their reservation, and join a waitlist when the workshop is full.

The main challenge is to keep every reservation correct when many users act at the same time. The system must never exceed its capacity, confirm an expired hold, or create duplicate reservations when a request is retried.

### Features to Implement

1. **Live Availability**

   - Display the number of available, held, and confirmed seats.
   - Show each user their reservation status and waitlist position.
   - Update availability for connected users without requiring a manual refresh.

2. **Seat Reservation**

   - Create a temporary hold when a seat is available and show its expiry time.
   - Require a server-validated user identity; allow only the owner of an active hold to confirm it and only the owner of an active hold or confirmed reservation to cancel it.
   - Release expired holds automatically and prevent them from being confirmed later.
   - Prevent a user from holding or confirming more than one seat.

3. **Waitlist**

   - Allow users to join a first-in, first-out (FIFO) waitlist when the workshop is full.
   - Prevent duplicate waitlist entries.
   - When a reservation is cancelled or a hold expires, promote the next eligible user exactly once.

4. **Reliable Backend**

   - Store reservation data in a database and handle all reservation actions on the server.
   - Use transactions, locking, database constraints, or another documented approach to prevent overbooking.
   - Accept an idempotency key for every state-changing request so that retrying it does not create another side effect.
   - Maintain an append-only activity timeline containing each reservation's previous state, new state, timestamp, and reason.
   - Recover expired holds correctly after the server restarts.

5. **Concurrency Test**

   - Include a repeatable test script or load-testing configuration that sends at least **100 simultaneous reservation attempts** for 20 seats.
   - The test should clearly verify that:
     - No more than 20 reservations are confirmed.
     - No user receives more than one active reservation.
     - Retrying the same idempotent request does not create a duplicate.
     - An expired hold cannot be confirmed.
     - A cancellation promotes only the next eligible waitlisted user.

### Tips

- Define the reservation states and valid transitions before implementing the API.
- Test with one or two seats first to make race conditions easier to reproduce.
- Use WebSockets, Server-Sent Events, or periodic polling for live updates.
- Enforce capacity in the backend and database, not through the interface alone.
- Document the database model, reservation lifecycle, idempotency strategy, and concurrency approach in the README.

### Useful Resources

- [PostgreSQL Transaction Isolation](https://www.postgresql.org/docs/current/transaction-iso.html)
- [PostgreSQL Explicit Locking](https://www.postgresql.org/docs/current/explicit-locking.html)
- [MDN: Using Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events)
- [MDN: WebSocket API](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)
- [k6 Documentation](https://grafana.com/docs/k6/latest/)
