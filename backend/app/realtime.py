from fastapi import WebSocket


# In-memory pub/sub broker managing client WebSocket connections.
# Note: In multi-instance deployments, back this with Redis Pub/Sub.
class ConnectionManager:
    def __init__(self) -> None:
        self.connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.connections.discard(websocket)

    # Fan-out event broadcast with dead client cleanup on broken pipes
    async def broadcast(self, payload: dict) -> None:
        dead: list[WebSocket] = []

        for websocket in list(self.connections):
            try:
                await websocket.send_json(payload)
            except Exception:
                dead.append(websocket)

        for websocket in dead:
            self.disconnect(websocket)


manager = ConnectionManager()