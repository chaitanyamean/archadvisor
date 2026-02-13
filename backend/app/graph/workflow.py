"""LangGraph workflow definition — wires agents into a graph with validation + debate loop.

The workflow:
1. Retrieve similar architectures (RAG)
2. Architect proposes initial design
3. **Validator checks design deterministically** (NEW)
4. If validation fails → Architect revises → re-validate (max 2 loops)
5. Devil's Advocate reviews (only sees validated designs)
6. Conditional: revise or proceed
7. Cost Analyzer estimates costs
8. Documentation agent produces final doc
"""

import json
from typing import Callable, Awaitable, Optional
from datetime import datetime

import structlog
from langgraph.graph import StateGraph, END

from app.graph.state import ArchAdvisorState, create_initial_state
from app.graph.nodes import (
    retrieve_context_node,
    architect_design_node,
    devils_advocate_review_node,
    architect_revise_node,
    cost_analysis_node,
    generate_docs_node,
    should_continue_debate,
)
from app.graph.validator_node import (
    validator_node,
    should_route_after_validation,
    architect_revise_from_validation_node,
)
from app.models.events import SessionCompleteEvent, ErrorEvent
from app.services.event_bus import event_bus

logger = structlog.get_logger()

EventCallback = Optional[Callable[[dict], Awaitable[None]]]


def build_graph() -> StateGraph:
    """Build the LangGraph workflow with validation gate.

    Flow:
        retrieve_context → architect_design → validator
            ├── FAIL → architect_revise_validation → validator (loop, max 2)
            └── PASS → devils_advocate_review
                           ├── revise → architect_revise → devils_advocate_review (loop, max 3)
                           └── proceed → cost_analysis → generate_docs → END
    """
    workflow = StateGraph(ArchAdvisorState)

    # Add nodes
    workflow.add_node("retrieve_context", retrieve_context_node)
    workflow.add_node("architect_design", architect_design_node)
    workflow.add_node("validator", validator_node)
    workflow.add_node("architect_revise_validation", architect_revise_from_validation_node)
    workflow.add_node("devils_advocate_review", devils_advocate_review_node)
    workflow.add_node("architect_revise", architect_revise_node)
    workflow.add_node("cost_analysis", cost_analysis_node)
    workflow.add_node("generate_docs", generate_docs_node)

    # ── Linear start ──
    workflow.set_entry_point("retrieve_context")
    workflow.add_edge("retrieve_context", "architect_design")

    # ── Architect → Validator ──
    workflow.add_edge("architect_design", "validator")

    # ── Validation Gate (conditional) ──
    workflow.add_conditional_edges(
        "validator",
        should_route_after_validation,
        {
            "pass_to_da": "devils_advocate_review",        # Passed — proceed to DA
            "revise": "architect_revise_validation",       # Failed — fix and re-validate
            "force_proceed": "devils_advocate_review",     # Max loops — proceed anyway
        },
    )

    # ── Validation revision loop ──
    workflow.add_edge("architect_revise_validation", "validator")

    # ── DA Debate Loop (conditional) ──
    workflow.add_conditional_edges(
        "devils_advocate_review",
        should_continue_debate,
        {
            "revise": "architect_revise",
            "proceed": "cost_analysis",
        },
    )
    workflow.add_edge("architect_revise", "devils_advocate_review")

    # ── Linear finish ──
    workflow.add_edge("cost_analysis", "generate_docs")
    workflow.add_edge("generate_docs", END)

    return workflow


def compile_graph():
    """Compile the workflow graph for execution."""
    graph = build_graph()
    return graph.compile()


# Module-level compiled graph (reused across sessions)
_compiled_graph = None


def get_compiled_graph():
    """Get or create the compiled graph singleton."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = compile_graph()
    return _compiled_graph


async def run_architecture_workflow(
    session_id: str,
    requirements: str,
    preferences: Optional[dict] = None,
    event_callback: EventCallback = None,
) -> ArchAdvisorState:
    """Execute the full architecture workflow.

    This is the main entry point called by the API layer.
    Nodes emit events directly via the event_bus singleton using session_id.
    The event_callback parameter is kept for backward compatibility but
    completion/error events are also emitted via event_bus.

    Args:
        session_id: Unique session identifier
        requirements: User's system requirements
        preferences: Optional preferences (cloud_provider, max_debate_rounds, etc.)
        event_callback: Optional async callback (kept for backward compat)

    Returns:
        Final workflow state with all agent outputs
    """
    logger.info(
        "workflow_started",
        session_id=session_id,
        requirements_length=len(requirements),
    )

    # Create the event_bus callback for this session
    cb = event_bus.create_callback(session_id)

    # Create initial state
    state = create_initial_state(session_id, requirements, preferences)

    try:
        graph = get_compiled_graph()

        # LangGraph's ainvoke runs the full graph.
        # Each node emits events via event_bus.create_callback(session_id).
        final_state = await graph.ainvoke(state)

        # Emit completion event
        duration = (
            datetime.fromisoformat(final_state["completed_at"])
            - datetime.fromisoformat(final_state["started_at"])
        ).total_seconds()

        await cb(
            SessionCompleteEvent(
                duration_seconds=round(duration, 2),
                total_cost_usd=round(final_state["total_cost_usd"], 4),
                debate_rounds=final_state["debate_round"],
                output_url=f"/api/v1/sessions/{session_id}/output",
            ).model_dump()
        )

        logger.info(
            "workflow_completed",
            session_id=session_id,
            debate_rounds=final_state["debate_round"],
            total_cost_usd=round(final_state["total_cost_usd"], 4),
            status=final_state["status"],
        )

        return final_state

    except Exception as e:
        logger.error("workflow_failed", session_id=session_id, error=str(e))

        await cb(
            ErrorEvent(
                message=f"Workflow failed: {str(e)}",
                recoverable=False,
            ).model_dump()
        )

        # Return error state
        state["status"] = "error"
        state["errors"] = state.get("errors", []) + [str(e)]
        state["completed_at"] = datetime.utcnow().isoformat()
        return state
