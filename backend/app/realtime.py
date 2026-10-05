from fastapi import WebSocket


class ConnectionManager:
    """
    Keeps track of currently connected WebSocket clients.
    """

    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """
        Accept a new WebSocket connection.
        """

        await websocket.accept()

        self.connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """
        Remove a disconnected client.
        """

        if websocket in self.connections:
            self.connections.remove(websocket)

    async def broadcast(self, message: dict):
        """
        Send a message to every connected client.
        """

        disconnected = []

        for websocket in self.connections:

            try:
                await websocket.send_json(message)

            except Exception:
                disconnected.append(websocket)

        for websocket in disconnected:
            self.disconnect(websocket)


manager = ConnectionManager()