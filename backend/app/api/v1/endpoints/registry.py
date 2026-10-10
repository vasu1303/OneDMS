from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.db import get_db_session
from app.api.v1.schemas.registry import (
    DealerResponse, DmsSystemCreate, DmsSystemResponse,
    MappingPreviewRequest, MappingPreviewResponse,
)
from app.services import registry


router = APIRouter()


@router.get("/dealers", response_model=list[DealerResponse])
async def list_dealers(db: AsyncSession = Depends(get_db_session)):
    return await registry.list_dealers(db)


@router.get("/dms-systems", response_model=list[DmsSystemResponse])
async def list_dms_systems(db: AsyncSession = Depends(get_db_session)):
    return await registry.list_dms_systems(db)


@router.post("/dms-systems", response_model=DmsSystemResponse, status_code=status.HTTP_201_CREATED)
async def create_dms_system(request: DmsSystemCreate, db: AsyncSession = Depends(get_db_session)):
    return await registry.create_dms_system(db, request)


@router.post("/dms-systems/preview", response_model=MappingPreviewResponse)
async def preview_mapping(request: MappingPreviewRequest):
    # Deliberately no session dependency: preview also works without a configured DB.
    return registry.preview_mapping(request)