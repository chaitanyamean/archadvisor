"""WebSocket event models for real-time agent streaming."""

from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime


class BaseEvent(BaseModel):
    """Base event model for all WebSocket events."""

    type: str
    timestamp: datetime = None

    def model_post_init(self, __context):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    def model_dump(self, **kwargs):
        """Override to always serialize datetimes as ISO strings for JSON safety."""
        kwargs.setdefault("mode", "json")
        return super().model_dump(**kwargs)


class AgentStartedEvent(BaseEvent):
    """Emitted when an agent begins processing."""

    type: Literal["agent_started"] = "agent_started"
    agent: str
    agent_label: str
    message: str


class AgentThinkingEvent(BaseEvent):
    """Emitted during agent processing to show progress."""

    type: Literal["agent_thinking"] = "agent_thinking"
    agent: str
    message: str


class AgentCompletedEvent(BaseEvent):
    """Emitted when an agent finishes processing."""

    type: Literal["agent_completed"] = "agent_completed"
    agent: str
    summary: str
    duration_seconds: float
    cost_usd: float


class DebateRoundStartedEvent(BaseEvent):
    """Emitted when a new debate round begins."""

    type: Literal["debate_round_started"] = "debate_round_started"
    round: int
    max_rounds: int
    message: str


class FindingDiscoveredEvent(BaseEvent):
    """Emitted when Devil's Advocate finds an issue."""

    type: Literal["finding_discovered"] = "finding_discovered"
    agent: str = "devils_advocate"
    severity: Literal["critical", "high", "medium", "low"]
    category: str
    component: str
    summary: str


class ArchitectDefendingEvent(BaseEvent):
    """Emitted when Architect responds to a finding."""

    type: Literal["architect_defending"] = "architect_defending"
    finding_id: str
    action: Literal["revised", "defended", "acknowledged"]
    message: str


class DebateRoundCompletedEvent(BaseEvent):
    """Emitted when a debate round finishes."""

    type: Literal["debate_round_completed"] = "debate_round_completed"
    round: int
    findings_total: int
    findings_critical: int
    findings_resolved: int
    next_action: Literal["revise", "proceed_to_costing"]


class WorkflowProgressEvent(BaseEvent):
    """Emitted to indicate overall workflow progress."""

    type: Literal["workflow_progress"] = "workflow_progress"
    step: int
    total_steps: int
    status: str
    message: str


class SessionCompleteEvent(BaseEvent):
    """Emitted when the full workflow completes."""

    type: Literal["session_complete"] = "session_complete"
    duration_seconds: float
    total_cost_usd: float
    debate_rounds: int
    output_url: str


class ErrorEvent(BaseEvent):
    """Emitted when an error occurs."""

    type: Literal["error"] = "error"
    message: str
    recoverable: bool = True
    retry_in_seconds: Optional[int] = None
