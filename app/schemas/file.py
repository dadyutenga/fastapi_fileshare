from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from uuid import UUID

class FileBase(BaseModel):
    filename: str
    original_filename: str
    file_size: int
    content_type: Optional[str] = None

class FileCreate(FileBase):
    ttl: int = 0
    is_public: bool = False

class FileResponse(FileBase):
    id: str  # Changed from int to str for UUID
    file_id: str
    upload_time: datetime
    ttl: int
    download_count: int
    is_active: bool
    is_public: bool
    owner_id: str  # Changed from int to str for UUID

    class Config:
        from_attributes = True

class FilePreview(BaseModel):
    file_id: str
    filename: str
    original_filename: str
    file_size: int
    content_type: Optional[str]
    upload_time: datetime
    download_count: int
    is_public: bool
    preview_type: str  # "image", "text", "pdf", "video", "audio", "archive", "office", "other"
    preview_content: Optional[str] = None
    can_preview: bool = True