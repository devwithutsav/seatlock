# Reservation lifecycle

```text
AVAILABLE --hold--> HELD --confirm--> CONFIRMED
                    |                   |
                    | expiry            | cancel
                    v                   v
                  EXPIRED            CANCELLED
                    |                   |
                    +------ seat free --+
                              |
                              v
                    promote next FIFO user
```

Rules:
- only the authenticated owner can confirm/cancel;
- one active (`HELD`/`CONFIRMED`) reservation per user;
- a hold cannot be confirmed after `held_until`;
- cancellation/expiry triggers at most one FIFO promotion for the freed seat.
