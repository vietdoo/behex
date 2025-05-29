from typing import Optional
from pydantic import BaseModel, ConfigDict
from datetime import datetime
import uuid


class FileBase(BaseModel):
    filename: str
    description: Optional[str] = None


class FileCreate(FileBase):
    pass


class FileUpdate(BaseModel):
    filename: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None


class File(FileBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    file_size: int
    content_type: str
    file_extension: Optional[str] = None
    object_name: str
    owner_id: int
    is_public: bool
    share_token: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class FileShare(BaseModel):
    share_url: str
    share_token: str
    expires_in: Optional[int] = None  # seconds 