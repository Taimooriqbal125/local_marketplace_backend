"""
WebSocket Package.
Provides real-time communication infrastructure.
"""

from .manager import ConnectionManager
from .events import NotificationEvent, SystemEvent, BaseWebsocketMessage

# Single global instance for easy import across services and routes
# We do NOT import handlers here to avoid circular dependencies with NotificationService
manager = ConnectionManager()
