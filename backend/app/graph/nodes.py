"""LangGraph node functions — each wraps an agent execution and updates state."""

import json
from typing import Callable, Awaitable, Optional

import structlog

from app.agents.architect import ArchitectAgent
from app.agents.devils_advocate import DevilsAdvocateAgent
from app.agents.cost_analyzer import CostAnalyzerAgent
from app.agents.documentation import DocumentationAgent
from app.graph.state import ArchAdvisorState, AgentMessage
from app.models.events import (
    WorkflowProgressEvent,
    DebateRoundStartedEvent,
    DebateRoundCompletedEvent,
    FindingDiscoveredEvent,
    ErrorEvent,
)
from app.services.event_bus import event_bus

logger = structlog.get_logger()

# Type alias for the event callback
EventCallback = Optional[Callable[[dict], Awaitable[None]]]

# Singleton agent instances
_architect = ArchitectAgent()
_devils_advocate = DevilsAdvocateAgent()
_cost_analyzer = CostAnalyzerAgent()
_documentation = DocumentationAgent()


async def retrieve_context_node(state: ArchAdvisorState) -> dict:
    """Retrieve similar past architectures from ChromaDB (RAG)."""
    cb = event_bus.create_callback(state["session_id"])
    await cb(
        WorkflowProgressEvent(
            step=1,
            total_steps=5,
            status="retrieving_context",
            message="Searching for similar past architectures...",
        ).model_dump()
    )

    # TODO: Implement ChromaDB retrieval
    # For now, return empty — the system works without RAG
    similar = []

    logger.info("context_retrieved", n_similar=len(similar), session_id=state["session_id"])

    return {
        "similar_architectures": similar,
        "status": "designing",
    }


async def architect_design_node(state: ArchAdvisorState) -> dict:
    """Architect proposes initial design."""
    cb = event_bus.create_callback(state["session_id"])
    await cb(
        WorkflowProgressEvent(
            step=2,
            total_steps=5,
            status="designing",
            message="Architect is designing the system architecture...",
        ).model_dump()
    )

    result = await _architect.run(state, cb)

    design_json = json.dumps(result["output"], indent=2)

    message = AgentMessage(
        agent="architect",
        role="Architect",
        summary=result["metadata"].get("summary", _architect._generate_summary(result["output"])),
        raw_output=design_json,
        timestamp=result["metadata"]["timestamp"],
        duration_seconds=result["metadata"]["duration_seconds"],
        model=result["metadata"]["model"],
        cost_usd=result["metadata"]["cost_usd"],
    )

    return {
        "current_design": design_json,
        "debate_round": 1,
        "status": "reviewing",
        "messages": state["messages"] + [message],
        "total_cost_usd": state["total_cost_usd"] + result["metadata"]["cost_usd"],
    }


async def devils_advocate_review_node(state: ArchAdvisorState) -> dict:
    """Devil's Advocate reviews the current design."""
    cb = event_bus.create_callback(state["session_id"])
    round_num = state["debate_round"]

    await cb(
        DebateRoundStartedEvent(
            round=round_num,
            max_rounds=state["max_debate_rounds"],
            message=f"Devil's Advocate is reviewing the design (round {round_num})...",
        ).model_dump()
    )

    result = await _devils_advocate.run(state, cb)
    review_json = json.dumps(result["output"], indent=2)

    # Emit individual findings as events
    findings = result["output"].get("findings", [])
    for finding in findings[:5]:  # Limit to top 5 for event stream
        await cb(
            FindingDiscoveredEvent(
                severity=finding.get("severity", "medium"),
                category=finding.get("category", "unknown"),
                component=finding.get("component", "unknown"),
                summary=finding.get("issue", ""),
            ).model_dump()
        )

    # Emit debate round summary
    severity = result["output"].get("severity_summary", {})
    recommendation = result["output"].get("proceed_recommendation", "revise_recommended")
    next_action = "proceed_to_costing" if recommendation == "proceed" else "revise"

    await cb(
        DebateRoundCompletedEvent(
            round=round_num,
            findings_total=sum(severity.values()),
            findings_critical=severity.get("critical", 0),
            findings_resolved=0,
            next_action=next_action,
        ).model_dump()
    )

    message = AgentMessage(
        agent="devils_advocate",
        role="Devil's Advocate",
        summary=_devils_advocate._generate_summary(result["output"]),
        raw_output=review_json,
        timestamp=result["metadata"]["timestamp"],
        duration_seconds=result["metadata"]["duration_seconds"],
        model=result["metadata"]["model"],
        cost_usd=result["metadata"]["cost_usd"],
    )

    return {
        "review_findings": review_json,
        "status": "revising",
        "messages": state["messages"] + [message],
        "total_cost_usd": state["total_cost_usd"] + result["metadata"]["cost_usd"],
    }


async def architect_revise_node(state: ArchAdvisorState) -> dict:
    """Architect revises design based on Devil's Advocate feedback."""
    cb = event_bus.create_callback(state["session_id"])
    await cb(
        WorkflowProgressEvent(
            step=2,
            total_steps=5,
            status="revising",
            message=f"Architect is revising the design (round {state['debate_round']})...",
        ).model_dump()
    )

    result = await _architect.run(state, cb)
    design_json = json.dumps(result["output"], indent=2)

    message = AgentMessage(
        agent="architect",
        role="Architect (Revision)",
        summary=f"Revised design: {_architect._generate_summary(result['output'])}",
        raw_output=design_json,
        timestamp=result["metadata"]["timestamp"],
        duration_seconds=result["metadata"]["duration_seconds"],
        model=result["metadata"]["model"],
        cost_usd=result["metadata"]["cost_usd"],
    )

    return {
        "current_design": design_json,
        "debate_round": state["debate_round"] + 1,
        "status": "reviewing",
        "messages": state["messages"] + [message],
        "total_cost_usd": state["total_cost_usd"] + result["metadata"]["cost_usd"],
    }


# async def cost_analysis_node(state: ArchAdvisorState) -> dict:
#     """Cost Analyzer estimates infrastructure costs."""
#     cb = event_bus.create_callback(state["session_id"])
#     await cb(
#         WorkflowProgressEvent(
#             step=4,
#             total_steps=5,
#             status="costing",
#             message="Cost Analyzer is estimating infrastructure costs across cloud providers...",
#         ).model_dump()
#     )

#     result = await _cost_analyzer.run(state, cb)
#     cost_json = json.dumps(result["output"], indent=2)

#     message = AgentMessage(
#         agent="cost_analyzer",
#         role="Cost Analyzer",
#         summary=_cost_analyzer._generate_summary(result["output"]),
#         raw_output=cost_json,
#         timestamp=result["metadata"]["timestamp"],
#         duration_seconds=result["metadata"]["duration_seconds"],
#         model=result["metadata"]["model"],
#         cost_usd=result["metadata"]["cost_usd"],
#     )

#     return {
#         "cost_analysis": cost_json,
#         "status": "documenting",
#         "messages": state["messages"] + [message],
#         "total_cost_usd": state["total_cost_usd"] + result["metadata"]["cost_usd"],
#     }

async def cost_analysis_node(state: ArchAdvisorState) -> dict:
    """Cost Analyzer estimates infrastructure costs. Currently disabled."""
    cb = event_bus.create_callback(state["session_id"])
    await cb(
        WorkflowProgressEvent(
            step=4,
            total_steps=5,
            status="costing",
            message="Cost analysis skipped (temporarily disabled).",
        ).model_dump()
    )

    logger.info("cost_analysis_skipped", session_id=state["session_id"])
    fallback = {"note": "Cost analysis temporarily disabled", "scale_tiers": [], "cost_optimization_tips": [], "cheapest_path": {}, "scaling_cost_projection": {}}
    message = AgentMessage(
        agent="cost_analyzer",
        role="Cost Analyzer",
        summary="Cost analysis skipped.",
        raw_output=json.dumps(fallback),
        timestamp=datetime.utcnow().isoformat(),
        duration_seconds=0,
        model="N/A",
        cost_usd=0,
    )
    return {
        "cost_analysis": json.dumps(fallback),
        "status": "documenting",
        "messages": state["messages"] + [message],
        "total_cost_usd": state["total_cost_usd"],
    }


async def generate_docs_node(state: ArchAdvisorState) -> dict:
    """Documentation agent produces the final architecture document."""
    cb = event_bus.create_callback(state["session_id"])
    await cb(
        WorkflowProgressEvent(
            step=5,
            total_steps=5,
            status="documenting",
            message="Documentation agent is producing the final architecture document...",
        ).model_dump()
    )

    result = await _documentation.run(state, cb)

    # Inject validation score into doc output for rendering
    doc_output = result["output"]
    if state.get("validation_score") is not None:
        doc_output["validation_score"] = state["validation_score"]
        doc_output["validation_passed"] = state.get("validation_passed", False)
        # Extract findings for the rendered document
        validation_report_json = state.get("validation_report", "")
        if validation_report_json:
            try:
                report_data = json.loads(validation_report_json)
                doc_output["validation_summary"] = report_data.get("summary", {})
                doc_output["validation_verdict"] = report_data.get("verdict", "")
                # Include top critical/high findings for visibility
                findings = []
                for err in report_data.get("errors", []):
                    if err.get("severity") in ("critical", "high"):
                        findings.append({
                            "severity": err["severity"],
                            "code": err.get("code", ""),
                            "message": err.get("message", ""),
                            "category": err.get("category"),
                            "evidence": err.get("evidence"),
                        })
                doc_output["validation_findings"] = findings
            except (json.JSONDecodeError, KeyError):
                pass

    doc_json = json.dumps(doc_output, indent=2)

    # Render to markdown
    rendered_md = _documentation.render_markdown(doc_output)

    # Extract diagrams
    diagrams = result["output"].get("diagrams", [])

    message = AgentMessage(
        agent="documentation",
        role="Documentation",
        summary=_documentation._generate_summary(result["output"]),
        raw_output=doc_json,
        timestamp=result["metadata"]["timestamp"],
        duration_seconds=result["metadata"]["duration_seconds"],
        model=result["metadata"]["model"],
        cost_usd=result["metadata"]["cost_usd"],
    )

    from datetime import datetime

    return {
        "final_document": doc_json,
        "rendered_markdown": rendered_md,
        "mermaid_diagrams": diagrams,
        "status": "complete",
        "completed_at": datetime.utcnow().isoformat(),
        "messages": state["messages"] + [message],
        "total_cost_usd": state["total_cost_usd"] + result["metadata"]["cost_usd"],
    }


def should_continue_debate(state: ArchAdvisorState) -> str:
    """Decide whether to continue the architect-DA debate or proceed to costing.

    Returns:
        "revise" — Architect needs to address critical findings
        "proceed" — Design is good enough, move to cost analysis
    """
    debate_round = state["debate_round"]
    max_rounds = state["max_debate_rounds"]

    # Hard limit on debate rounds
    if debate_round >= max_rounds:
        logger.info(
            "debate_max_rounds_reached",
            round=debate_round,
            max=max_rounds,
            session_id=state["session_id"],
        )
        return "proceed"

    # Parse the DA's latest findings
    try:
        findings = json.loads(state.get("review_findings", "{}"))
        critical_count = findings.get("severity_summary", {}).get("critical", 0)
        recommendation = findings.get("proceed_recommendation", "revise_recommended")

        # Proceed if no critical issues or DA recommends proceeding
        if critical_count == 0 or recommendation == "proceed":
            logger.info(
                "debate_proceeding",
                round=debate_round,
                critical=critical_count,
                recommendation=recommendation,
                session_id=state["session_id"],
            )
            return "proceed"

        logger.info(
            "debate_continuing",
            round=debate_round,
            critical=critical_count,
            recommendation=recommendation,
            session_id=state["session_id"],
        )
        return "revise"

    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("debate_parse_error", error=str(e), session_id=state["session_id"])
        return "proceed"  # On error, proceed rather than loop
