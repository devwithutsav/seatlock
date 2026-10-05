"""
WebSocket connection manager.
"""

from fastapi import WebSocket


class ConnectionManager:

    def __init__(self):
        self.active_connections: list[WebSocket] = []


    async def connect(
        self,
        websocket: WebSocket,
    ):
        await websocket.accept()

        self.active_connections.append(
            websocket
        )


    def disconnect(
        self,
        websocket: WebSocket,
    ):
        if websocket in self.active_connections:
            self.active_connections.remove(
                websocket
            )


    async def broadcast(
        self,
        message: dict,
    ):
        """
        Broadcast an event to all currently connected clients.
        """

        disconnected = []

        for websocket in list(
            self.active_connections
        ):

            try:

                await websocket.send_json(
                    message
                )

            except Exception:

                disconnected.append(
                    websocket
                )

        for websocket in disconnected:
            self.disconnect(websocket)


manager = ConnectionManager()