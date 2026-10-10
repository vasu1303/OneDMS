"""Registry operations without settings, environment reads, or AI dependencies."""

from contextlib import suppress
from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.registry import (
    DealerResponse, DmsSystemCreate, DmsSystemResponse, MappingPreviewRequest,
    MappingPreviewResponse,
)
from app.models.invoice import Dealer, DmsSystem, MappingConfig
from app.services.mapping import MappingError, map_source_to_canonical, resolve_path


def dms_response(dms: DmsSystem, mapping: MappingConfig | None) -> DmsSystemResponse:
    return DmsSystemResponse(
        id=dms.id, name=dms.name, integration_tier=dms.integration_tier,
        integration_method=dms.integration_method, input_format=dms.input_format,
        active_mapping_version=mapping.version if mapping is not None else None,
        active_mapping_config=mapping.mapping_config if mapping is not None else None,
    )


async def list_dealers(db: AsyncSession) -> list[DealerResponse]:
    try:
        result = await db.execute(select(Dealer).order_by(Dealer.id))
        return [DealerResponse.model_validate(row) for row in result.scalars().all()]
    except SQLAlchemyError:
        raise HTTPException(500, "Unable to list dealers.") from None


async def list_dms_systems(db: AsyncSession) -> list[DmsSystemResponse]:
    # Filter in the JOIN so systems without an active invoice mapping remain visible.
    query = select(DmsSystem, MappingConfig).outerjoin(MappingConfig, and_(
        MappingConfig.dms_id == DmsSystem.id,
        MappingConfig.mapping_direction == "SOURCE_TO_CANONICAL",
        MappingConfig.document_type == "INVOICE",
        MappingConfig.is_active.is_(True),
    )).order_by(DmsSystem.id)
    try:
        result = await db.execute(query)
        return [dms_response(dms, mapping) for dms, mapping in result.all()]
    except SQLAlchemyError:
        raise HTTPException(500, "Unable to list DMS systems.") from None


async def create_dms_system(db: AsyncSession, request: DmsSystemCreate) -> DmsSystemResponse:
    dms = DmsSystem(
        name=request.name, integration_tier=request.integration_tier,
        integration_method=request.integration_method, input_format=request.input_format,
    )
    try:
        db.add(dms)
        await db.flush()
        mapping = MappingConfig(
            mapping_name=f"DMS {dms.id} invoice v1",
            mapping_direction="SOURCE_TO_CANONICAL", dms_id=dms.id,
            target_system=None, document_type="INVOICE", version=1, is_active=True,
            mapping_config=request.mapping_config.mapper_config()
            if request.mapping_config is not None else {},
        )
        db.add(mapping)
        await db.flush()
        # Materialize before commit: no expired ORM reads or post-commit DB failures.
        response = dms_response(dms, mapping)
        await db.commit()
        return response
    except Exception as exc:
        # A rollback failure must not replace the sanitized original error.
        with suppress(Exception):
            await db.rollback()
        if isinstance(exc, IntegrityError):
            raise HTTPException(409, "DMS system or mapping conflicts with existing data.") from None
        raise HTTPException(500, "Unable to create DMS system and mapping.") from None


def preview_mapping(request: MappingPreviewRequest) -> MappingPreviewResponse:
    config = request.mapping_config.mapper_config()
    errors: list[dict[str, str]] = []

    def check_path(data: dict[str, Any], field: str, path: str) -> None:
        if resolve_path(data, path) is None:
            errors.append({"field": field, "message": "Configured source path is missing or null."})

    for field, path in config.items():
        if field != "line_items":
            check_path(request.payload, field, path)
    line_config = config["line_items"]
    lines = resolve_path(request.payload, line_config["source_field"])
    if not isinstance(lines, list):
        errors.append({"field": "line_items", "message": "Configured source path must contain a list."})
    else:
        for index, line in enumerate(lines):
            if not isinstance(line, dict):
                errors.append({"field": f"line_items[{index}]", "message": "Line item must be an object."})
                continue
            for field, path in line_config.items():
                if field != "source_field":
                    check_path(line, f"line_items[{index}].{field}", path)
    if errors:
        raise HTTPException(422, {"message": "Mapping preview failed.", "errors": errors})

    try:
        candidate = map_source_to_canonical(request.payload, config)
    except (MappingError, ValueError, TypeError, ArithmeticError) as exc:
        field = "payload"
        if isinstance(exc, MappingError):
            for name, path in config.items():
                if name != "line_items" and path == exc.path:
                    field = name
                    break
            else:
                for index in range(len(lines)):
                    for name, path in line_config.items():
                        if name != "source_field" and exc.path == f"{line_config['source_field']}[{index}].{path}":
                            field = f"line_items[{index}].{name}"
        # Never echo exception text, source values, credentials, or provider bodies.
        raise HTTPException(422, {
            "message": "Mapping preview failed.",
            "errors": [{"field": field, "message": "Source value cannot be normalized for this field."}],
        }) from None
    return MappingPreviewResponse(canonical_candidate=candidate)