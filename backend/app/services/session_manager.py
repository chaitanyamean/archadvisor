"""Session manager — Redis-backed session state CRUD."""

import json
from typing import Optional
from datetime import datetime

import structlog

logger = structlog.get_logger()

# Session TTL: 24 hours
SESSION_TTL = 86400


class SessionManager:
    """Manages architecture session state in Redis."""

    def __init__(self, redis_client):
        self.redis = redis_client
        self._prefix = "archadvisor:session:"

    def _key(self, session_id: str) -> str:
        return f"{self._prefix}{session_id}"

    async def create(self, session_id: str, state: dict) -> None:
        """Store initial session state."""
        key = self._key(session_id)
        # Store as JSON string
        await self.redis.setex(key, SESSION_TTL, json.dumps(state, default=str))

        # Add to recent sessions list
        await self.redis.lpush(f"{self._prefix}recent", session_id)
        await self.redis.ltrim(f"{self._prefix}recent", 0, 99)  # Keep last 100

        logger.info("session_created", session_id=session_id)

    async def get(self, session_id: str) -> Optional[dict]:
        """Retrieve session state."""
        key = self._key(session_id)
        data = await self.redis.get(key)
        if data is None:
            return None
        return json.loads(data)

    async def update(self, session_id: str, updates: dict) -> None:
        """Update session state with partial updates."""
        current = await self.get(session_id)
        if current is None:
            raise ValueError(f"Session {session_id} not found")

        current.update(updates)
        key = self._key(session_id)
        await self.redis.setex(key, SESSION_TTL, json.dumps(current, default=str))

    async def update_status(self, session_id: str, status: str) -> None:
        """Quick status update."""
        await self.update(session_id, {"status": status})

    async def add_message(self, session_id: str, message: dict) -> None:
        """Append an agent message to session history."""
        current = await self.get(session_id)
        if current is None:
            raise ValueError(f"Session {session_id} not found")

        messages = current.get("messages", [])
        messages.append(message)
        await self.update(session_id, {"messages": messages})

    async def store_output(self, session_id: str, state: dict) -> None:
        """Store the final workflow output."""
        await self.update(session_id, {
            "status": state.get("status", "complete"),
            "current_design": state.get("current_design"),
            "review_findings": state.get("review_findings"),
            "cost_analysis": state.get("cost_analysis"),
            "final_document": state.get("final_document"),
            "rendered_markdown": state.get("rendered_markdown"),
            "mermaid_diagrams": state.get("mermaid_diagrams", []),
            "messages": state.get("messages", []),
            "debate_round": state.get("debate_round", 0),
            "total_cost_usd": state.get("total_cost_usd", 0),
            "completed_at": state.get("completed_at"),
        })

    async def list_recent(self, limit: int = 20) -> list[str]:
        """List recent session IDs."""
        return await self.redis.lrange(f"{self._prefix}recent", 0, limit - 1)

    async def delete(self, session_id: str) -> None:
        """Delete a session."""
        key = self._key(session_id)
        await self.redis.delete(key)
        logger.info("session_deleted", session_id=session_id)

    async def exists(self, session_id: str) -> bool:
        """Check if a session exists."""
        key = self._key(session_id)
        return await self.redis.exists(key)
