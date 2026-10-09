from fastapi import FastAPI
from contextlib import AsyncExitStack, asynccontextmanager
from app.core.config import settings
from app.core.database import create_database, create_session_factory
from app.core.logging import log
from app.services.storage import create_storage
from app.middleware.cors import setup_cors
from app.exceptions.handlers import register_exception_handlers
from app.api.v1.router import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info(f"Starting {settings.APP_NAME}")
    app.state.database = None
    app.state.db_session_factory = None
    app.state.object_storage = None
    app.state.infrastructure_errors = {}
    async with AsyncExitStack() as resources:
        try:
            engine = create_database(settings)
            if engine is not None:
                resources.push_async_callback(engine.dispose)
                app.state.database = engine
                app.state.db_session_factory = create_session_factory(engine)
        except Exception:
            app.state.infrastructure_errors["database"] = "configuration_error"
            log.warning("Database configuration could not be initialized")
        try:
            storage = create_storage(settings)
            if storage is not None:
                resources.push_async_callback(storage.close)
                app.state.object_storage = storage
        except Exception:
            app.state.infrastructure_errors["object_storage"] = "configuration_error"
            log.warning("Object storage configuration could not be initialized")
        try:
            yield
        finally:
            log.info(f"Stopping {settings.APP_NAME}")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

setup_cors(app)
register_exception_handlers(app)

app.include_router(api_router, prefix=settings.API_PREFIX)

@app.get("/")
async def root():
    return {
        "message": f"{settings.APP_NAME} API",
        "version": settings.VERSION,
        "docs_url": "/docs"
    }
