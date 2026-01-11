from datetime import datetime, timedelta
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
import uuid
from app.database import Base


class Asset(Base):
    __tablename__ = "assets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    size = Column(Integer, nullable=False)
    etag = Column(String(255), nullable=False, unique=True)
    object_key = Column(String(500), nullable=False, unique=True)
    version = Column(Integer, default=1, nullable=False)
    is_public = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    versions = relationship("AssetVersion", back_populates="asset", cascade="all, delete-orphan")
    tokens = relationship("AccessToken", back_populates="asset", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Asset {self.id}>"


class AssetVersion(Base):
    __tablename__ = "asset_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    asset_id = Column(String(36), ForeignKey("assets.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    object_key = Column(String(500), nullable=False, unique=True)
    etag = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    asset = relationship("Asset", back_populates="versions")

    def __repr__(self):
        return f"<AssetVersion {self.id} (v{self.version_number})>"


class AccessToken(Base):
    __tablename__ = "access_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    token = Column(String(500), nullable=False, unique=True, index=True)
    asset_id = Column(String(36), ForeignKey("assets.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)

    asset = relationship("Asset", back_populates="tokens")

    def is_valid(self) -> bool:
        return not self.is_revoked and datetime.utcnow() < self.expires_at

    def __repr__(self):
        return f"<AccessToken {self.id}>"
