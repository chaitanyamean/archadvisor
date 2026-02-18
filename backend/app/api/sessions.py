"""Sessions API — create, get status, get output, list sessions."""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Query

import structlog

from app.models.requests import CreateSessionRequest
from app.models.responses import (
    CreateSessionResponse,
    SessionStatusResponse,
    SessionOutputResponse,
    SessionOutputMetadata,
    SessionProgress,
    AgentMessageResponse,
    DiagramOutput,
    TemplateResponse,
)
from app.services.rate_limiter import rate_limiter
from app.services.event_bus import event_bus
from app.graph.workflow import run_architecture_workflow
from app.graph.state import create_initial_state

logger = structlog.get_logger()

router = APIRouter()


def _generate_session_id() -> str:
    """Generate a short, readable session ID."""
    return f"arch_{uuid.uuid4().hex[:8]}"


# ─── Sample Templates ───

TEMPLATES = [
    TemplateResponse(
        id="notification_system",
        name="Real-Time Notification System",
        description="E-commerce notification system with push, email, SMS, and in-app channels",
        complexity="complex",
        requirements=(
            "Design a real-time notification system for an e-commerce platform.\n\n"
            "Requirements:\n"
            "- 50M registered users, 5M DAU\n"
            "- Push notifications, email, SMS, in-app\n"
            "- User preference management (opt-in/out per channel)\n"
            "- Rate limiting to prevent notification fatigue\n"
            "- Multi-region deployment (US, EU, Asia)\n"
            "- Sub-500ms delivery for push notifications\n"
            "- Event-driven architecture\n"
            "- Delivery tracking and analytics"
        ),
    ),
    TemplateResponse(
        id="payment_gateway",
        name="Payment Processing Gateway",
        description="PCI-compliant payment gateway with multi-currency support",
        complexity="complex",
        requirements=(
            "Design a payment processing gateway for a marketplace platform.\n\n"
            "Requirements:\n"
            "- Process 10K transactions/minute at peak\n"
            "- Support credit cards, debit cards, UPI, bank transfers\n"
            "- Multi-currency (USD, EUR, GBP, INR)\n"
            "- PCI DSS Level 1 compliance\n"
            "- Idempotent transaction processing\n"
            "- Split payments (marketplace takes commission)\n"
            "- Real-time fraud detection\n"
            "- Reconciliation and settlement system\n"
            "- 99.99% uptime SLA"
        ),
    ),
    TemplateResponse(
        id="chat_platform",
        name="Real-Time Chat Platform",
        description="Scalable chat platform with group chats, media sharing, and E2E encryption",
        complexity="medium",
        requirements=(
            "Design a real-time chat platform similar to Slack/Discord.\n\n"
            "Requirements:\n"
            "- 1M concurrent users\n"
            "- 1:1 and group chats (up to 500 members)\n"
            "- Media sharing (images, files up to 100MB)\n"
            "- Message search across history\n"
            "- Read receipts and typing indicators\n"
            "- End-to-end encryption for 1:1 chats\n"
            "- Push notifications for offline users\n"
            "- Message retention: 1 year"
        ),
    ),
    TemplateResponse(
        id="data_pipeline",
        name="Real-Time Data Pipeline",
        description="Event streaming pipeline for analytics with sub-second latency",
        complexity="medium",
        requirements=(
            "Design a real-time data pipeline for an analytics platform.\n\n"
            "Requirements:\n"
            "- Ingest 1M events/second from web and mobile clients\n"
            "- Sub-second latency for real-time dashboards\n"
            "- Batch processing for historical analysis\n"
            "- Schema evolution support\n"
            "- Data quality validation and dead-letter queues\n"
            "- Multi-tenant isolation\n"
            "- GDPR compliance (data deletion, export)\n"
            "- 30-day hot storage, 2-year cold storage"
        ),
    ),
]


# ─── Endpoints ───


@router.get("/templates", response_model=list[TemplateResponse])
async def list_templates():
    """List available requirement templates for demo purposes."""
    return TEMPLATES


@router.post("/sessions", status_code=202, response_model=CreateSessionResponse)
async def create_session(
    request_body: CreateSessionRequest,
    background_tasks: BackgroundTasks,
    request: Request,
):
    """Create a new architecture design session.

    This kicks off the multi-agent workflow in the background.
    Connect to the WebSocket endpoint to receive real-time events.
    """
    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.allow_request(client_ip):
        remaining = rate_limiter.remaining(client_ip)
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "message": f"Maximum {rate_limiter.max_requests} sessions per day. Try again later.",
                "remaining": remaining,
                "retry_after_seconds": int(rate_limiter.reset_time(client_ip)),
            },
        )

    session_id = _generate_session_id()
    now = datetime.utcnow()

    # Create initial state and store in Redis
    initial_state = create_initial_state(
        session_id=session_id,
        requirements=request_body.requirements,
        preferences=request_body.preferences.model_dump(),
    )
    initial_state["client_ip"] = client_ip

    session_manager = request.app.state.session_manager
    await session_manager.create(session_id, initial_state)

    # Create event callback that broadcasts to WebSocket + updates Redis
    async def workflow_event_callback(event: dict):
        await event_bus.publish(session_id, event)

    # Kick off workflow in background
    async def run_workflow_background():
        try:
            final_state = await run_architecture_workflow(
                session_id=session_id,
                requirements=request_body.requirements,
                preferences=request_body.preferences.model_dump(),
                event_callback=workflow_event_callback,
            )
            # Store final output in Redis
            await session_manager.store_output(session_id, final_state)
        except Exception as e:
            logger.error("workflow_background_error", session_id=session_id, error=str(e))
            await session_manager.update_status(session_id, "error")

    background_tasks.add_task(run_workflow_background)

    logger.info(
        "session_created",
        session_id=session_id,
        requirements_length=len(request_body.requirements),
        client_ip=client_ip,
    )

    return CreateSessionResponse(
        session_id=session_id,
        status="designing",
        created_at=now,
        websocket_url=f"/ws/sessions/{session_id}",
        estimated_duration_seconds=120,
        estimated_cost_usd=0.18,
    )


@router.get("/sessions/{session_id}", response_model=SessionStatusResponse)
async def get_session_status(session_id: str, request: Request):
    """Get session status and agent conversation history."""
    session_manager = request.app.state.session_manager
    session = await session_manager.get(session_id)

    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    # Build message responses
    messages = []
    for msg in session.get("messages", []):
        messages.append(
            AgentMessageResponse(
                agent=msg.get("agent", "unknown"),
                role=msg.get("role", "Unknown"),
                summary=msg.get("summary", ""),
                timestamp=msg.get("timestamp", datetime.utcnow().isoformat()),
                duration_seconds=msg.get("duration_seconds", 0),
                model=msg.get("model", "unknown"),
                cost_usd=msg.get("cost_usd", 0),
            )
        )

    # Determine current step
    status = session.get("status", "designing")
    step_map = {
        "initializing": 0,
        "retrieving_context": 1,
        "designing": 2,
        "validating": 3,
        "reviewing": 3,
        "revising": 3,
        "costing": 4,
        "documenting": 5,
        "complete": 5,
        "error": -1,
        "cancelled": -1,
    }

    # Determine current agent
    agent_map = {
        "designing": "architect",
        "validating": "validator",
        "reviewing": "devils_advocate",
        "revising": "architect",
        "costing": "cost_analyzer",
        "documenting": "documentation",
    }

    return SessionStatusResponse(
        session_id=session_id,
        status=status,
        progress=SessionProgress(
            current_agent=agent_map.get(status),
            debate_round=session.get("debate_round", 0),
            steps_completed=step_map.get(status, 0),
            total_steps=5,
        ),
        messages=messages,
        cost_so_far_usd=session.get("total_cost_usd", 0),
        created_at=session.get("started_at", datetime.utcnow().isoformat()),
        completed_at=session.get("completed_at"),
    )


@router.get("/sessions/{session_id}/output", response_model=SessionOutputResponse)
async def get_session_output(session_id: str, request: Request):
    """Download the final architecture document."""
    session_manager = request.app.state.session_manager
    session = await session_manager.get(session_id)

    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    if session.get("status") != "complete":
        raise HTTPException(
            status_code=409,
            detail=f"Session is not complete. Current status: {session.get('status')}",
        )

    # Build diagrams
    diagrams = [
        DiagramOutput(
            type=d.get("type", "component"),
            title=d.get("title", "Diagram"),
            mermaid_code=d.get("mermaid_code", ""),
        )
        for d in session.get("mermaid_diagrams", [])
    ]

    # Collect unique models used
    models_used = list(set(
        msg.get("model", "unknown") for msg in session.get("messages", [])
    ))

    # Calculate duration
    started = session.get("started_at", "")
    completed = session.get("completed_at", "")
    try:
        duration = (
            datetime.fromisoformat(completed) - datetime.fromisoformat(started)
        ).total_seconds()
    except (ValueError, TypeError):
        duration = 0

    return SessionOutputResponse(
        session_id=session_id,
        format="markdown",
        document=session.get("rendered_markdown", "# No document generated"),
        diagrams=diagrams,
        metadata=SessionOutputMetadata(
            total_duration_seconds=round(duration, 2),
            total_cost_usd=round(session.get("total_cost_usd", 0), 4),
            debate_rounds=session.get("debate_round", 0),
            models_used=models_used,
        ),
    )


@router.post("/sessions/{session_id}/cancel")
async def cancel_session(session_id: str, request: Request):
    """Cancel a running session."""
    session_manager = request.app.state.session_manager
    session = await session_manager.get(session_id)

    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    if session.get("status") in ("complete", "error", "cancelled"):
        raise HTTPException(
            status_code=409,
            detail=f"Session is already {session.get('status')}",
        )

    await session_manager.update(session_id, {
        "status": "cancelled",
        "completed_at": datetime.utcnow().isoformat(),
    })

    # Notify WebSocket clients
    await event_bus.publish(session_id, {
        "type": "session_cancelled",
        "message": "Session was cancelled by user",
    })

    return {"session_id": session_id, "status": "cancelled"}


@router.get("/sessions", response_model=list[SessionStatusResponse])
async def list_sessions(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
):
    """List recent architecture sessions for the requesting client's IP."""
    client_ip = request.client.host if request.client else "unknown"
    session_manager = request.app.state.session_manager
    session_ids = await session_manager.list_recent(limit * 5)  # fetch more to filter

    sessions = []
    for sid in session_ids:
        if isinstance(sid, bytes):
            sid = sid.decode()
        session = await session_manager.get(sid)
        if session and session.get("client_ip") == client_ip:
            status = session.get("status", "designing")
            sessions.append(
                SessionStatusResponse(
                    session_id=sid,
                    status=status,
                    progress=SessionProgress(
                        debate_round=session.get("debate_round", 0),
                        steps_completed=0,
                        total_steps=5,
                    ),
                    cost_so_far_usd=session.get("total_cost_usd", 0),
                    created_at=session.get("started_at", datetime.utcnow().isoformat()),
                    completed_at=session.get("completed_at"),
                )
            )
            if len(sessions) >= limit:
                break

    return sessions
