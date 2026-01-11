from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class AssetResponse(BaseModel):
    id: str
    filename: str
    mime_type: str
    size: int
    etag: str
    version: int
    is_public: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AssetVersionResponse(BaseModel):
    id: str
    asset_id: str
    version_number: int
    etag: str
    created_at: datetime

    class Config:
        from_attributes = True


class AccessTokenResponse(BaseModel):
    token: str
    expires_at: datetime

    class Config:
        from_attributes = True


class PublishResponse(BaseModel):
    version_id: str
    version_number: int
    etag: str
    url: str
