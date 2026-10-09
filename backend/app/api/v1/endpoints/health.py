import asyncio
from collections.abc import Awaitable, Callable
from time import perf_counter

from fastapi import APIRouter, Request, Response
from app.core.config import settings
from app.core.database import check_database
from app.api.v1.schemas.health import DependencyHealth, DependencyStatus

router = APIRouter()

@router.get("/")
async def health_check():
    return {"status": "healthy", "version": settings.VERSION}


async def probe(check: Callable[[], Awaitable[None]]) -> DependencyStatus:
    started = perf_counter()
    try:
        await asyncio.wait_for(check(), timeout=settings.DEPENDENCY_TIMEOUT_SECONDS)
        status = "healthy"
    except TimeoutError:
        status = "timeout"
    except Exception:
        status = "failed"
    return DependencyStatus(
        status=status,
        latency_ms=round((perf_counter() - started) * 1000, 2),
    )


@router.get(
    "/dependencies",
    response_model=DependencyHealth,
    responses={503: {"model": DependencyHealth, "description": "A dependency is unavailable"}},
)
async def dependency_health(request: Request, response: Response):
    state = request.app.state
    errors = getattr(state, "infrastructure_errors", {})
    database = getattr(state, "database", None)
    storage = getattr(state, "object_storage", None)

    async def check_service(name, client, check):
        if name in errors:
            return DependencyStatus(status="configuration_error")
        if client is None:
            return DependencyStatus(status="not_configured")
        return await probe(check)

    db_status, storage_status = await asyncio.gather(
        check_service("database", database, lambda: check_database(database)),
        check_service("object_storage", storage, lambda: storage.check()),
    )
    healthy = db_status.status == storage_status.status == "healthy"
    response.status_code = 200 if healthy else 503
    response.headers["Cache-Control"] = "no-store"
    return DependencyHealth(
        status="healthy" if healthy else "unhealthy",
        database=db_status,
        object_storage=storage_status,
    )
