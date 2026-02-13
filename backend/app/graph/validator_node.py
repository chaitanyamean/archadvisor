"""Validator Node — bridges the deterministic validation engine into the LangGraph workflow.

This node runs AFTER the Architect and BEFORE the Devil's Advocate.
It acts as a quality gate: if critical issues exist, the design goes back
to the Architect for revision WITHOUT burning an LLM call on the DA.
"""

import json
from typing import Callable, Awaitable, Optional

import structlog

from app.validators import validation_engine, ValidationReport
from app.graph.state import ArchAdvisorState, AgentMessage
from app.models.events import (
    AgentStartedEvent,
    AgentCompletedEvent,
    WorkflowProgressEvent,
    FindingDiscoveredEvent,
)
from app.services.event_bus import event_bus

logger = structlog.get_logger()

EventCallback = Optional[Callable[[dict], Awaitable[None]]]


async def validator_node(state: ArchAdvisorState) -> dict:
    """Run deterministic validation on the current architecture design.

    This node:
    1. Parses the current design JSON
    2. Runs all validators (< 50ms, no LLM calls)
    3. Emits events for each finding
    4. Returns validation report in state

    The workflow uses the report to decide:
    - PASS (no critical, score >= 60) → proceed to Devil's Advocate
    - FAIL → route back to Architect with validation errors
    """
    cb = event_bus.create_callback(state["session_id"])
    await cb(
        AgentStartedEvent(
            agent="validator",
            agent_label="Design Validator",
            message="Running deterministic validation checks...",
        ).model_dump()
    )

    # Parse design
    design = state.get("current_design", "{}")
    requirements = state.get("requirements", "")

    # Check if this is a re-validation (after revision)
    previous_report_json = state.get("validation_report")
    previous_report = None
    if previous_report_json:
        try:
            previous_report = ValidationReport(**json.loads(previous_report_json))
        except Exception:
            pass

    # Run validation
    if previous_report:
        report = validation_engine.validate_with_context(design, requirements, previous_report)
    else:
        report = validation_engine.validate(design, requirements)

    # Emit findings as events
    for error in report.errors[:8]:  # Limit event stream to top 8
        await cb(
            FindingDiscoveredEvent(
                agent="validator",
                severity=error.severity,
                category=error.code,
                component=error.component or "architecture",
                summary=error.message,
            ).model_dump()
        )

    # Emit completion
    await cb(
        AgentCompletedEvent(
            agent="validator",
            summary=(
                f"Score: {report.score}/100 | "
                f"{report.summary['critical']} critical, "
                f"{report.summary['high']} high, "
                f"{report.summary['medium']} medium | "
                f"{'PASS' if report.passed else 'FAIL'}"
            ),
            duration_seconds=0.05,  # Deterministic, always fast
            cost_usd=0.0,           # No LLM calls
        ).model_dump()
    )

    # Build message for conversation history
    message = AgentMessage(
        agent="validator",
        role="Design Validator",
        summary=report.verdict,
        raw_output=report.model_dump_json(),
        timestamp=__import__("datetime").datetime.utcnow().isoformat(),
        duration_seconds=0.05,
        model="deterministic",
        cost_usd=0.0,
    )

    logger.info(
        "validation_complete",
        session_id=state["session_id"],
        passed=report.passed,
        score=report.score,
        summary=report.summary,
    )

    return {
        "validation_report": report.model_dump_json(),
        "validation_passed": report.passed,
        "validation_score": report.score,
        "messages": state["messages"] + [message],
        # Status depends on pass/fail — but workflow routing handles this
        "status": "reviewing" if report.passed else "revising",
    }


def should_route_after_validation(state: ArchAdvisorState) -> str:
    """Decide routing after validation.

    Returns:
        "pass_to_da" — Design passed validation, proceed to Devil's Advocate
        "revise" — Critical issues found, send back to Architect
        "force_proceed" — Max revision loops reached, proceed anyway
    """
    validation_passed = state.get("validation_passed", True)
    validation_round = state.get("validation_round", 0)
    max_validation_rounds = 2  # Cap at 2 revision loops to prevent infinite cycling

    if validation_passed:
        logger.info(
            "validation_routing",
            decision="pass_to_da",
            round=validation_round,
            session_id=state["session_id"],
        )
        return "pass_to_da"

    if validation_round >= max_validation_rounds:
        logger.warning(
            "validation_max_rounds",
            round=validation_round,
            session_id=state["session_id"],
        )
        return "force_proceed"

    logger.info(
        "validation_routing",
        decision="revise",
        round=validation_round,
        session_id=state["session_id"],
    )
    return "revise"


async def architect_revise_from_validation_node(state: ArchAdvisorState) -> dict:
    """Architect revises design based on VALIDATOR feedback (not DA feedback).

    This is separate from the DA-triggered revision because:
    1. The prompt includes validator errors (deterministic, specific)
    2. The architect gets structured error codes, not subjective feedback
    3. We increment validation_round, not debate_round
    """
    from app.agents.architect import ArchitectAgent

    cb = event_bus.create_callback(state["session_id"])
    await cb(
        WorkflowProgressEvent(
            step=2,
            total_steps=6,
            status="revising",
            message="Architect is fixing validation errors...",
        ).model_dump()
    )

    # Build a special state that includes validation errors
    validation_report = state.get("validation_report", "{}")
    enriched_state = {
        **state,
        "review_findings": validation_report,  # Reuse the review_findings field
        "debate_round": 1,  # Trigger revision mode in architect
    }

    architect = ArchitectAgent()
    result = await architect.run(enriched_state, cb)

    design_json = json.dumps(result["output"], indent=2)

    message = AgentMessage(
        agent="architect",
        role="Architect (Validation Fix)",
        summary=f"Revised design to fix validation errors: {result['output'].get('overview', '')[:100]}",
        raw_output=design_json,
        timestamp=result["metadata"]["timestamp"],
        duration_seconds=result["metadata"]["duration_seconds"],
        model=result["metadata"]["model"],
        cost_usd=result["metadata"]["cost_usd"],
    )

    return {
        "current_design": design_json,
        "validation_round": state.get("validation_round", 0) + 1,
        "status": "validating",
        "messages": state["messages"] + [message],
        "total_cost_usd": state["total_cost_usd"] + result["metadata"]["cost_usd"],
    }
