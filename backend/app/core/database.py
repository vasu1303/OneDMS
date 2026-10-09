from sqlalchemy import URL, create_engine, make_url, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings


def database_url(value: str) -> URL:
    url = make_url(value)
    if url.drivername not in {"postgres", "postgresql", "postgresql+psycopg"}:
        raise ValueError("A PostgreSQL connection string is required")
    if not url.host or not url.database:
        raise ValueError("Database host and name are required")
    if url.query.get("sslmode") not in {"require", "verify-ca", "verify-full"}:
        raise ValueError("An encrypted PostgreSQL connection is required")
    return url.set(drivername="postgresql+psycopg")


def create_database(settings: Settings) -> AsyncEngine | None:
    value = settings.DATABASE_URL.get_secret_value()
    if not value:
        return None
    return create_async_engine(
        database_url(value),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=0,
        pool_timeout=settings.DEPENDENCY_TIMEOUT_SECONDS,
        connect_args={
            "connect_timeout": max(2, int(settings.DEPENDENCY_TIMEOUT_SECONDS)),
            "prepare_threshold": None,
        },
        hide_parameters=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)


def create_sync_database(settings: Settings) -> Engine:
    value = settings.DATABASE_URL.get_secret_value()
    if not value:
        raise ValueError("DATABASE_URL must be configured")
    return create_engine(
        database_url(value),
        poolclass=NullPool,
        connect_args={
            "connect_timeout": max(2, int(settings.DEPENDENCY_TIMEOUT_SECONDS)),
            "prepare_threshold": None,
        },
        hide_parameters=True,
    )


async def check_database(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        result = await connection.execute(text("SELECT 1"))
        if result.scalar_one() != 1:
            raise RuntimeError("Unexpected database probe result")