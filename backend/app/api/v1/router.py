from fastapi import APIRouter
from app.api.v1.endpoints import documents, health, invoices, registry

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
api_router.include_router(registry.router, tags=["registry"])

