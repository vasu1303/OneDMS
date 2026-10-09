from typing import Literal

from pydantic import BaseModel


class DependencyStatus(BaseModel):
    status: Literal["healthy", "failed", "timeout", "not_configured", "configuration_error"]
    latency_ms: float | None = None


class DependencyHealth(BaseModel):
    status: Literal["healthy", "unhealthy"]
    database: DependencyStatus
    object_storage: DependencyStatus