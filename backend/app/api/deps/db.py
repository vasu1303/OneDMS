from collections.abc import AsyncIterator

from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory = getattr(request.app.state, "db_session_factory", None)
    if factory is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    async with factory() as session:
        yield session