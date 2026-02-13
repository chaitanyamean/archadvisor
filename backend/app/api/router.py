"""Main API router — combines all endpoint routers."""

from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.sessions import router as sessions_router
from app.api.websocket import router as websocket_router

api_router = APIRouter()

# Health check
api_router.include_router(health_router, tags=["Health"])

# Sessions CRUD
api_router.include_router(sessions_router, tags=["Sessions"])

# WebSocket is exported separately — mounted at app root (no /api/v1 prefix)
ws_router = websocket_router
