from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.logging import log
from app.middleware.cors import setup_cors
from app.exceptions.handlers import register_exception_handlers
from app.api.v1.router import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info(f"Starting {settings.APP_NAME}")
    yield
    log.info(f"Stopping {settings.APP_NAME}")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

setup_cors(app)
register_exception_handlers(app)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)

@app.get("/")
async def root():
    return {
        "message": f"{settings.APP_NAME} API",
        "version": settings.VERSION,
        "docs_url": "/docs"
    }
