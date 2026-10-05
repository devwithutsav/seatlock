# Real-time updates

`/ws` is a FastAPI WebSocket endpoint. The backend broadcasts events after successful transaction commits for holds, confirmations, cancellations, expirations, waitlist changes, and promotions.

The React client listens for these events and refetches authoritative state. A slow fallback poll runs every 10 seconds only as resilience if a socket reconnect is needed; manual refresh is not required.
