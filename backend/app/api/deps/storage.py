from fastapi import HTTPException, Request
from app.services.storage import ObjectStorage

def get_storage(request: Request) -> ObjectStorage:
    storage = getattr(request.app.state, "object_storage", None)
    if storage is None:
        raise HTTPException(status_code=503, detail="Object storage is not configured")
    return storage
