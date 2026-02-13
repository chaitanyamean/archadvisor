"""ArchAdvisor — Multi-Agent Architecture Design System.

Main FastAPI application with lifespan management, CORS, and global error handling.
"""

from contextlib import asynccontextmanager

import structlog
import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.api.router import api_router, ws_router
from app.services.session_manager import SessionManager

# Configure structured logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if get_settings().DEBUG else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        structlog.get_config()["wrapper_class"].level if hasattr(structlog.get_config().get("wrapper_class", object), "level") else 0
    ),
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    settings = get_settings()

    # ── Startup ──
    logger.info("app_starting", debug=settings.DEBUG)

    # Initialize Redis
    try:
        app.state.redis = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            encoding="utf-8",
        )
        await app.state.redis.ping()
        logger.info("redis_connected", url=settings.REDIS_URL)
    except Exception as e:
        logger.error("redis_connection_failed", error=str(e))
        # App can still start — sessions will fail gracefully
        app.state.redis = None

    # Initialize Session Manager
    app.state.session_manager = SessionManager(app.state.redis)

    logger.info("app_started")

    yield

    # ── Shutdown ──
    logger.info("app_shutting_down")

    if app.state.redis:
        await app.state.redis.close()
        logger.info("redis_disconnected")

    logger.info("app_stopped")


# ── Create Application ──

app = FastAPI(
    title="ArchAdvisor",
    description=(
        "Multi-agent AI architecture design system. "
        "Four specialized agents collaborate through debate and review "
        "to produce comprehensive system architecture documents."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ── Middleware ──

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global Exception Handlers ──

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all error handler for unhandled exceptions."""
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        error_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred. Please try again.",
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle validation errors."""
    return JSONResponse(
        status_code=422,
        content={"error": "validation_error", "message": str(exc)},
    )


# ── Routes ──

app.include_router(api_router, prefix="/api/v1")
app.include_router(ws_router)  # WebSocket at /ws/sessions/{id} (no versioned prefix)


# ── Root endpoint ──

@app.get("/")
async def root():
    """Root endpoint — API info."""
    return {
        "name": "ArchAdvisor",
        "version": "1.0.0",
        "description": "Multi-agent AI architecture design system",
        "docs": "/docs",
        "health": "/api/v1/health",
    }
