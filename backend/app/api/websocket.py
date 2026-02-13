"""WebSocket endpoint for real-time agent event streaming."""

import json
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Optional

import structlog

from app.services.event_bus import event_bus

logger = structlog.get_logger()

router = APIRouter()


def _json_serial(obj):
    """JSON serializer for objects not serializable by default json code."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


async def _send_json(websocket: WebSocket, data: dict):
    """Send JSON over WebSocket with datetime handling."""
    text = json.dumps(data, default=_json_serial)
    await websocket.send_text(text)


@router.websocket("/ws/sessions/{session_id}")
async def session_websocket(websocket: WebSocket, session_id: str):
    """WebSocket connection for streaming agent events in real-time.

    Protocol:
        Server → Client: JSON events (agent_started, finding_discovered, etc.)
        Client → Server: JSON commands (cancel, force_proceed)

    Reconnection:
        On connect, server sends all historical events for this session,
        so late joiners or reconnecting clients get the full picture.
    """
    await websocket.accept()
    logger.info("ws_connected", session_id=session_id)

    # Create a listener that forwards events to this WebSocket
    async def ws_listener(event: dict):
        await _send_json(websocket, event)

    # Subscribe to events
    event_bus.subscribe(session_id, ws_listener)

    try:
        # Send historical events (for reconnecting clients)
        history = event_bus.get_history(session_id)
        if history:
            await _send_json(websocket, {
                "type": "event_history",
                "events": history,
                "count": len(history),
            })

        # Keep connection alive and listen for client commands
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                msg_type = message.get("type")

                if msg_type == "cancel":
                    logger.info("ws_cancel_requested", session_id=session_id)
                    await _send_json(websocket, {
                        "type": "info",
                        "message": "Cancellation requested",
                    })

                elif msg_type == "force_proceed":
                    logger.info("ws_force_proceed", session_id=session_id)
                    await _send_json(websocket, {
                        "type": "info",
                        "message": "Force proceed requested",
                    })

                elif msg_type == "ping":
                    await _send_json(websocket, {"type": "pong"})

            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await _send_json(websocket, {
                    "type": "error",
                    "message": "Invalid JSON",
                })

    except WebSocketDisconnect:
        pass
    finally:
        event_bus.unsubscribe(session_id, ws_listener)
        logger.info("ws_disconnected", session_id=session_id)
