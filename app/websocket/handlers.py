"""
WebSocket Message Handlers — processes incoming messages from clients.
"""

from typing import Any, Dict
from uuid import UUID

from fastapi import WebSocket
from sqlalchemy.orm import Session


async def handle_websocket_message(
    websocket: WebSocket, 
    user_id: UUID, 
    data: Dict[str, Any], 
    db: Session
):
    """
    Core routing logic for incoming WebSocket messages.
    Parses the 'event' type and performs corresponding actions.
    """
    # Import service inside to avoid circular dependency with WebSocket manager
    from app.services.notification_service import NotificationService
    
    event_type = data.get("event")
    payload = data.get("data", {})

    if not event_type:
        await websocket.send_json({
            "event": "error",
            "data": {"message": "Missing 'event' field in message"}
        })
        return

    # Example: Manual mark as read via WebSocket
    if event_type == "mark_as_read":
        notification_id_str = payload.get("notificationId")
        if notification_id_str:
            try:
                notification_id = UUID(notification_id_str)
                service = NotificationService(db)
                service.mark_as_read(notification_id, current_user_id=user_id)
                
                await websocket.send_json({
                    "event": "acknowledge",
                    "data": {"message": "Notification marked as read", "id": notification_id_str}
                })
            except Exception as e:
                await websocket.send_json({
                    "event": "error",
                    "data": {"message": f"Failed to mark as read: {str(e)}"}
                })

    # Add more event handlers here (e.g., chat_message, typing_status, etc.)
    else:
        await websocket.send_json({
            "event": "error",
            "data": {"message": f"Unknown event type: {event_type}"}
        })
