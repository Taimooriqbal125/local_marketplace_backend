"""
WebSocket Routes — API endpoints for real-time communication.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.websocket import manager
from app.websocket.handlers import handle_websocket_message

router = APIRouter(
    prefix="/ws",
    tags=["WebSocket"],
)


async def get_token_user_id(token: str) -> Optional[uuid.UUID]:
    """Helper to manually validate JWT token from query params."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            return None
        return uuid.UUID(user_id)
    except (JWTError, ValueError):
        return None


@router.websocket("/")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token for authentication"),
    db: Session = Depends(get_db),
):
    """
    The main WebSocket endpoint for real-time updates.
    Expects authentication token as a query parameter.
    """
    user_id = await get_token_user_id(token)
    
    if not user_id:
        # If token is invalid, we close the connection immediately
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Accept connection and track it in our manager
    await manager.connect(websocket, user_id)
    
    try:
        while True:
            # Wait for messages from the client
            data = await websocket.receive_json()
            
            # Delegate processing to our handlers
            await handle_websocket_message(
                websocket=websocket,
                user_id=user_id,
                data=data,
                db=db
            )
            
    except WebSocketDisconnect:
        # Clean up when client leaves
        manager.disconnect(websocket, user_id)
    except Exception:
        # Catch-all for other errors to ensure cleanup
        manager.disconnect(websocket, user_id)
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
