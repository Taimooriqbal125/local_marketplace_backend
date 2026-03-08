"""
WebSocket Connection Manager — handles active connections and broadcasting.
"""

import json
from typing import Dict, List
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect


class ConnectionManager:
    """
    Manages active WebSocket connections by mapping User IDs to their active sockets.
    One user can have multiple active connections (e.g., mobile and web).
    """

    def __init__(self) -> None:
        # Map user_id (UUID) -> List of active WebSocket objects
        self.active_connections: Dict[UUID, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: UUID):
        """Accept connection and store the socket for the user."""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: UUID):
        """Remove the socket from the user's connection list."""
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            
            # Clean up empty lists
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_personal_message(self, user_id: UUID, message: dict):
        """Send a JSON message to all active connections of a specific user."""
        if user_id in self.active_connections:
            # We iterate over a copy to avoid issues if a socket disconnects during loop
            for connection in self.active_connections[user_id][:]:
                try:
                    await connection.send_json(message)
                except Exception:
                    # If sending fails, assume the connection is dead and clean up
                    self.disconnect(connection, user_id)

    async def broadcast(self, message: dict):
        """Send a message to EVERYONE currently connected."""
        for user_id, connections in self.active_connections.items():
            for connection in connections[:]:
                try:
                    await connection.send_json(message)
                except Exception:
                    self.disconnect(connection, user_id)

    def get_active_user_count(self) -> int:
        """Return count of users currently online."""
        return len(self.active_connections)
