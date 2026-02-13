"""Health check endpoint."""

import time
from fastapi import APIRouter, Request

from app.models.responses import HealthResponse, HealthDependency

router = APIRouter()

_start_time = time.time()


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    """System health check with dependency status."""
    dependencies = {}

    # Check Redis
    try:
        redis = request.app.state.redis
        start = time.time()
        await redis.ping()
        latency = (time.time() - start) * 1000
        dependencies["redis"] = HealthDependency(status="healthy", latency_ms=round(latency, 2))
    except Exception as e:
        dependencies["redis"] = HealthDependency(status="unhealthy", message=str(e))

    # Overall status
    all_healthy = all(d.status == "healthy" for d in dependencies.values())
    any_unhealthy = any(d.status == "unhealthy" for d in dependencies.values())

    if all_healthy:
        status = "healthy"
    elif any_unhealthy:
        status = "degraded"
    else:
        status = "unhealthy"

    return HealthResponse(
        status=status,
        uptime_seconds=round(time.time() - _start_time, 2),
        dependencies=dependencies,
    )
