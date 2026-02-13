"""API response models."""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


class CreateSessionResponse(BaseModel):
    """Response after creating a new session."""

    session_id: str
    status: str = "designing"
    created_at: datetime
    websocket_url: str
    estimated_duration_seconds: int = 120
    estimated_cost_usd: float = 0.18


class AgentMessageResponse(BaseModel):
    """Single agent message in session history."""

    agent: str
    role: str
    summary: str
    timestamp: datetime
    duration_seconds: float
    model: str
    cost_usd: float = 0.0


class SessionProgress(BaseModel):
    """Current progress of a session."""

    current_agent: Optional[str] = None
    debate_round: int = 0
    steps_completed: int = 0
    total_steps: int = 5


class SessionStatusResponse(BaseModel):
    """Full session status with conversation history."""

    session_id: str
    status: Literal[
        "initializing", "retrieving_context", "designing", "validating",
        "reviewing", "revising", "costing", "documenting",
        "complete", "error", "cancelled",
    ]
    progress: SessionProgress
    messages: list[AgentMessageResponse] = []
    cost_so_far_usd: float = 0.0
    created_at: datetime
    completed_at: Optional[datetime] = None


class DiagramOutput(BaseModel):
    """A generated architecture diagram."""

    type: str  # "component", "sequence", "deployment"
    title: str
    mermaid_code: str


class SessionOutputMetadata(BaseModel):
    """Metadata about the generation run."""

    total_duration_seconds: float
    total_cost_usd: float
    debate_rounds: int
    models_used: list[str]


class SessionOutputResponse(BaseModel):
    """Final architecture output."""

    session_id: str
    format: str = "markdown"
    document: str
    diagrams: list[DiagramOutput] = []
    metadata: SessionOutputMetadata


class HealthDependency(BaseModel):
    """Health status of a single dependency."""

    status: Literal["healthy", "unhealthy", "degraded"]
    latency_ms: Optional[float] = None
    message: Optional[str] = None


class HealthResponse(BaseModel):
    """System health check response."""

    status: Literal["healthy", "unhealthy", "degraded"]
    version: str = "1.0.0"
    uptime_seconds: float
    dependencies: dict[str, HealthDependency]


class TemplateResponse(BaseModel):
    """A sample requirements template."""

    id: str
    name: str
    description: str
    requirements: str
    complexity: Literal["simple", "medium", "complex"]
