import hashlib
import json
import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.db import get_db_session
from app.api.deps.storage import get_storage
from app.api.v1.schemas.documents import DocumentResponse, JsonSubmissionRequest
from app.extraction.models import DocumentFormat
from app.extraction.service import extraction_service
from app.models.invoice import Dealer, DmsSystem, InboundDocument, StandardizedInvoice
from app.services.storage import ObjectStorage

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
FILE_FORMATS = {
    DocumentFormat.PDF: (".pdf", "application/pdf"),
    DocumentFormat.CSV: (".csv", "text/csv"),
    DocumentFormat.JSON: (".json", "application/json"),
    DocumentFormat.EXCEL: (".xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
}

@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    dealer_id: Annotated[int, Form()],
    dms_id: Annotated[int, Form()],
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session),
    storage: ObjectStorage = Depends(get_storage),
):
    """
    Upload a document (PDF, CSV, JSON).
    """
    # Validate Dealer and DMS existence
    dealer = await db.get(Dealer, dealer_id)
    if not dealer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dealer not found.")
    
    dms = await db.get(DmsSystem, dms_id)
    if not dms:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DMS System not found.")

    # Read and validate size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds the 10MB limit."
        )

    document_format = extraction_service.detect_format(
        content,
        filename=file.filename,
        content_type=file.content_type,
    )
    if document_format not in FILE_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type. Upload a PDF, CSV, JSON, XLS, or XLSX file.",
        )
    if dms.input_format != document_format.value.upper():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Uploaded {document_format.value.upper()} file does not match the selected {dms.input_format} DMS profile.",
        )

    # Generate checksum
    checksum = hashlib.sha256(content).hexdigest()

    # Generate unique storage key to avoid overwriting
    ext, normalized_mime_type = FILE_FORMATS[document_format]
    if document_format == DocumentFormat.EXCEL and file.filename and file.filename.lower().endswith(".xls"):
        ext, normalized_mime_type = ".xls", "application/vnd.ms-excel"
    file_id = str(uuid.uuid4())
    storage_key = f"inbound/{dealer_id}/{dms_id}/{file_id}{ext}"

    # Try uploading to storage first
    try:
        await storage.upload_file(storage_key, content, normalized_mime_type)
    except Exception as e:
        logger.error(f"Storage upload failed for key {storage_key}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to upload document to storage."
        )

    # Create document record
    doc = InboundDocument(
        dealer_id=dealer_id,
        dms_id=dms_id,
        original_file_name=file.filename,
        mime_type=normalized_mime_type,
        file_size_bytes=len(content),
        storage_key=storage_key,
        checksum_sha256=checksum,
        status="RECEIVED",
    )
    db.add(doc)
    
    try:
        await db.commit()
        await db.refresh(doc)
    except Exception as e:
        await db.rollback()
        logger.error(f"Database commit failed for document {storage_key}: {e}")
        # Best effort orphan cleanup
        await storage.delete_file(storage_key)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while saving document metadata."
        )

    return doc

@router.post("/json", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def submit_json_document(
    request: JsonSubmissionRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Submit a JSON payload directly.
    """
    # Validate Dealer and DMS existence
    dealer = await db.get(Dealer, request.dealer_id)
    if not dealer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dealer not found.")
    
    dms = await db.get(DmsSystem, request.dms_id)
    if not dms:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DMS System not found.")
    if dms.input_format != "JSON":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="JSON payload submission requires a JSON DMS profile.",
        )

    content = json.dumps(request.payload).encode("utf-8")
    checksum = hashlib.sha256(content).hexdigest()

    doc = InboundDocument(
        dealer_id=request.dealer_id,
        dms_id=request.dms_id,
        original_file_name="payload.json",
        mime_type="application/json",
        file_size_bytes=len(content),
        raw_payload=request.payload,
        storage_key=None,
        checksum_sha256=checksum,
        status="RECEIVED",
    )
    db.add(doc)
    
    try:
        await db.commit()
        await db.refresh(doc)
    except Exception as e:
        await db.rollback()
        logger.error(f"Database commit failed for JSON payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while saving document metadata."
        )

    return doc

@router.get("/{document_id}/source")
async def get_document_source(
    document_id: int,
    db: AsyncSession = Depends(get_db_session),
    storage: ObjectStorage = Depends(get_storage),
):
    """
    Stream the source document from storage or DB.
    """
    doc = await db.get(InboundDocument, document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    if not doc.storage_key:
        # If it's a JSON payload without storage key, stream the raw_payload directly
        if doc.raw_payload:
            content = json.dumps(doc.raw_payload).encode("utf-8")
            
            async def json_streamer():
                yield content
                
            return StreamingResponse(
                json_streamer(),
                media_type="application/json",
                headers={"Content-Disposition": f'inline; filename="{doc.original_file_name or "document.json"}"'}
            )
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not available.")

    try:
        stream_generator, content_type = await storage.get_file_stream(doc.storage_key)
    except Exception as e:
        logger.error(f"Failed to retrieve source for key {doc.storage_key}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to retrieve document from storage."
        )

    safe_filename = doc.original_file_name or f"document_{document_id}"
    # Sanitize filename to avoid header injection
    safe_filename = safe_filename.replace('"', '').replace('\n', '').replace('\r', '')

    return StreamingResponse(
        stream_generator,
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{safe_filename}"'}
    )


@router.get("")
async def list_documents(
    processing_status: str | None = None,
    validation_status: str | None = None,
    review_status: str | None = None,
    dealer_code: str | None = None,
    dealer_id: int | None = None,
    q: str | None = None,
    page: int = 1,
    size: int = 20,
    db: AsyncSession = Depends(get_db_session),
):
    """
    List inbound documents with filtering for status, dealer, and text search.
    Supports pagination and returns items envelope.
    """
    from sqlalchemy.orm import selectinload
    from app.services.workflow import serialize_document_for_frontend

    query = (
        select(InboundDocument)
        .options(
            selectinload(InboundDocument.dealer),
            selectinload(InboundDocument.dms),
            selectinload(InboundDocument.invoice).selectinload(StandardizedInvoice.line_items),
        )
        .order_by(InboundDocument.received_at.desc())
    )

    if dealer_id:
        query = query.where(InboundDocument.dealer_id == dealer_id)

    if processing_status and processing_status != "all":
        status_map = {
            "received": "RECEIVED",
            "processing": "PROCESSING",
            "processed": "COMPLETED",
            "review_required": "REVIEW_REQUIRED",
            "failed": "FAILED",
        }
        db_stat = status_map.get(processing_status.lower(), processing_status.upper())
        query = query.where(InboundDocument.status == db_stat)

    if dealer_code:
        query = query.join(InboundDocument.dealer).where(Dealer.dealer_code.ilike(f"%{dealer_code}%"))

    if q:
        query = query.where(InboundDocument.original_file_name.ilike(f"%{q}%"))

    # Pagination
    offset = max(0, (page - 1) * size)
    query = query.offset(offset).limit(size)

    docs = (await db.execute(query)).scalars().all()
    items = [serialize_document_for_frontend(d) for d in docs]

    return {"items": items, "total": len(items), "page": page, "size": size}


@router.get("/{document_id}")
async def get_document_detail(
    document_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Retrieve single document detail with associated dealer, dms, and invoice info.
    """
    from sqlalchemy.orm import selectinload
    from app.services.workflow import serialize_document_for_frontend

    stmt = (
        select(InboundDocument)
        .options(
            selectinload(InboundDocument.dealer),
            selectinload(InboundDocument.dms),
            selectinload(InboundDocument.invoice).selectinload(StandardizedInvoice.line_items),
        )
        .where(InboundDocument.id == document_id)
    )
    doc = (await db.execute(stmt)).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    return serialize_document_for_frontend(doc)


@router.post("/{document_id}/process")
async def process_document_workflow(
    document_id: int,
    force: bool = False,
    db: AsyncSession = Depends(get_db_session),
    storage: ObjectStorage = Depends(get_storage),
):
    """
    Orchestrate extraction, mapping, validation, and persistence for an inbound document.
    Idempotent: prevents duplicate invoices and updates statuses consistently.
    """
    from app.services.workflow import WorkflowService

    return await WorkflowService.process_document(
        session=db,
        document_id=document_id,
        storage=storage,
        force=force,
    )

