"""API request models."""

from pydantic import BaseModel, Field
from typing import Optional, Literal


class SessionPreferences(BaseModel):
    """Optional preferences for architecture generation."""

    cloud_provider: Optional[Literal["aws", "gcp", "azure", "all"]] = "all"
    max_debate_rounds: int = Field(default=3, ge=1, le=5)
    output_format: Literal["markdown", "pdf"] = "markdown"
    detail_level: Literal["brief", "detailed", "comprehensive"] = "detailed"


class CreateSessionRequest(BaseModel):
    """Request to create a new architecture session."""

    requirements: str = Field(
        ...,
        min_length=50,
        max_length=10000,
        description="System requirements in natural language",
        examples=[
            "Design a real-time notification system for an e-commerce platform "
            "with 50M registered users, 5M DAU. Support push notifications, email, "
            "SMS, and in-app. Multi-region deployment with sub-500ms push delivery."
        ],
    )
    preferences: SessionPreferences = Field(default_factory=SessionPreferences)


class CancelSessionRequest(BaseModel):
    """Request to cancel a running session."""

    reason: Optional[str] = None
