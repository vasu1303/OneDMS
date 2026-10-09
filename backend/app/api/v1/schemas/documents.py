from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

class DocumentResponse(BaseModel):
    id: int
    status: str
    original_file_name: Optional[str] = None
    mime_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    checksum_sha256: Optional[str] = None
    received_at: datetime

    model_config = ConfigDict(from_attributes=True)

class JsonSubmissionRequest(BaseModel):
    dealer_id: int
    dms_id: int
    payload: dict[str, Any]
