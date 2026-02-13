"""Event bus — internal pub/sub for broadcasting WebSocket events to connected clients."""

import asyncio
from typing import Callable, Awaitable, Dict, Set
from collections import defaultdict

import structlog

logger = structlog.get_logger()

# Type alias for event listeners
EventListener = Callable[[dict], Awaitable[None]]


class EventBus:
    """In-memory pub/sub for routing agent events to WebSocket connections.

    Each session_id can have multiple listeners (multiple browser tabs, etc.).
    Events are fire-and-forget — if a listener fails, it's removed.
    """

    def __init__(self):
        self._listeners: Dict[str, Set[EventListener]] = defaultdict(set)
        self._event_history: Dict[str, list] = defaultdict(list)
        self._max_history = 100  # Keep last 100 events per session

    def subscribe(self, session_id: str, listener: EventListener) -> None:
        """Subscribe a listener to events for a session."""
        self._listeners[session_id].add(listener)
        logger.debug("event_bus_subscribe", session_id=session_id, total_listeners=len(self._listeners[session_id]))

    def unsubscribe(self, session_id: str, listener: EventListener) -> None:
        """Unsubscribe a listener from a session."""
        self._listeners[session_id].discard(listener)
        if not self._listeners[session_id]:
            del self._listeners[session_id]

    async def publish(self, session_id: str, event: dict) -> None:
        """Publish an event to all listeners for a session."""
        # Store in history for late joiners
        self._event_history[session_id].append(event)
        if len(self._event_history[session_id]) > self._max_history:
            self._event_history[session_id] = self._event_history[session_id][-self._max_history:]

        # Broadcast to all listeners
        dead_listeners = set()
        for listener in self._listeners.get(session_id, set()):
            try:
                await listener(event)
            except Exception as e:
                logger.warning("event_listener_failed", session_id=session_id, error=str(e))
                dead_listeners.add(listener)

        # Clean up dead listeners
        for dead in dead_listeners:
            self._listeners[session_id].discard(dead)

    def get_history(self, session_id: str) -> list[dict]:
        """Get event history for a session (for reconnecting clients)."""
        return list(self._event_history.get(session_id, []))

    def create_callback(self, session_id: str) -> Callable[[dict], Awaitable[None]]:
        """Create an event callback function for use in workflow nodes.

        This is the bridge between the LangGraph workflow and the WebSocket layer.

        Usage:
            callback = event_bus.create_callback(session_id)
            await run_architecture_workflow(..., event_callback=callback)
        """
        async def callback(event: dict) -> None:
            await self.publish(session_id, event)

        return callback

    def cleanup(self, session_id: str) -> None:
        """Clean up all resources for a session."""
        self._listeners.pop(session_id, None)
        self._event_history.pop(session_id, None)


# Module-level singleton
event_bus = EventBus()
