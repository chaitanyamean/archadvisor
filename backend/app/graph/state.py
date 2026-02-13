"""Shared workflow state schema for LangGraph."""

from typing import TypedDict, Literal, Optional, Any
from datetime import datetime


class AgentMessage(TypedDict):
    """Record of a single agent execution."""

    agent: str
    role: str
    summary: str
    raw_output: str
    timestamp: str
    duration_seconds: float
    model: str
    cost_usd: float


class ArchAdvisorState(TypedDict):
    """Full workflow state passed between LangGraph nodes.

    LangGraph requires all state to be in a single TypedDict.
    Each node reads what it needs and writes its outputs.
    """

    # ── Input ──
    requirements: str
    preferences: dict  # cloud_provider, max_debate_rounds, detail_level
    session_id: str

    # ── RAG Context ──
    similar_architectures: list[str]

    # ── Agent Outputs ──
    current_design: Optional[str]       # Latest architecture JSON (updated after each revision)
    review_findings: Optional[str]      # Latest DA review JSON
    cost_analysis: Optional[str]        # Cost Analyzer output JSON
    final_document: Optional[str]       # Documentation agent output JSON
    rendered_markdown: Optional[str]    # Final rendered markdown document

    # ── Diagrams ──
    mermaid_diagrams: list[dict]        # [{type, title, mermaid_code}]

    # ── Conversation History ──
    messages: list[AgentMessage]

    # ── Validation ──
    validation_report: Optional[str]    # ValidationReport JSON
    validation_passed: Optional[bool]   # Did the design pass validation?
    validation_score: Optional[float]   # Architecture quality score 0-100
    validation_round: int               # Number of validator → architect loops

    # ── Control Flow ──
    debate_round: int
    max_debate_rounds: int
    status: Literal[
        "initializing",
        "retrieving_context",
        "designing",
        "validating",
        "reviewing",
        "revising",
        "costing",
        "documenting",
        "complete",
        "error",
        "cancelled",
    ]

    # ── Error Tracking ──
    errors: list[str]

    # ── Metadata ──
    started_at: str
    completed_at: Optional[str]
    total_cost_usd: float


def create_initial_state(
    session_id: str,
    requirements: str,
    preferences: Optional[dict] = None,
) -> ArchAdvisorState:
    """Create the initial state for a new architecture session."""
    prefs = preferences or {}
    return ArchAdvisorState(
        requirements=requirements,
        preferences=prefs,
        session_id=session_id,
        similar_architectures=[],
        current_design=None,
        review_findings=None,
        cost_analysis=None,
        final_document=None,
        rendered_markdown=None,
        mermaid_diagrams=[],
        messages=[],
        validation_report=None,
        validation_passed=None,
        validation_score=None,
        validation_round=0,
        debate_round=0,
        max_debate_rounds=prefs.get("max_debate_rounds", 3),
        status="initializing",
        errors=[],
        started_at=datetime.utcnow().isoformat(),
        completed_at=None,
        total_cost_usd=0.0,
    )
