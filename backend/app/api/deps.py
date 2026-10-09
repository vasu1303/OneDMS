from collections.abc import AsyncGenerator
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.handlers import OneDMSException


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides an asynchronous database session.

    Yields an AsyncSession from the application's session factory.
    Rolls back any uncommitted changes on exception and closes the session.
    """
    session_factory = getattr(request.app.state, "db_session_factory", None)
    if session_factory is None:
        raise OneDMSException("Database connection is not configured or unavailable", status_code=503)

    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

