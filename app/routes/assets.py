from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Response, Header
from sqlalchemy.orm import Session
import uuid
from app.database import get_db
from app.models.asset import Asset, AssetVersion, AccessToken
from app.schemas import AssetResponse, PublishResponse, AccessTokenResponse
from app.services.storage import storage_service
from app.services.cdn import cdn_service
from app.utils.security import generate_etag, generate_access_token, create_token_expiry
from app.utils.caching import generate_cache_control_header, should_return_304, get_last_modified_header
from app.config import CDN_ENDPOINT
from datetime import datetime

router = APIRouter(prefix="/assets", tags=["assets"])


@router.post("/upload")
async def upload_asset(
    file: UploadFile = File(...),
    is_public: bool = False,
    db: Session = Depends(get_db)
) -> AssetResponse:
    """Upload a new asset to object storage and create metadata."""
    content = await file.read()
    
    if not content:
        raise HTTPException(status_code=400, detail="File is empty")
    
    # Generate ETag from content
    etag = generate_etag(content)
    
    # Create object key
    object_key = f"assets/{uuid.uuid4()}/{file.filename}"
    
    # Upload to storage
    success = await storage_service.upload_file(
        object_key,
        content,
        file.content_type or "application/octet-stream"
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to upload file to storage")
    
    # Create asset record
    asset = Asset(
        id=str(uuid.uuid4()),
        filename=file.filename,
        mime_type=file.content_type or "application/octet-stream",
        size=len(content),
        etag=etag,
        object_key=object_key,
        version=1,
        is_public=is_public
    )
    
    db.add(asset)
    db.commit()
    db.refresh(asset)
    
    return AssetResponse.model_validate(asset)


@router.head("/assets/{asset_id}/download")
async def head_asset(
    asset_id: str,
    db: Session = Depends(get_db)
):
    """Check for asset modifications without downloading content."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    return Response(
        headers={
            "ETag": asset.etag,
            "Last-Modified": get_last_modified_header(asset.updated_at),
            "Cache-Control": generate_cache_control_header(asset.is_public),
            "Content-Type": asset.mime_type,
            "Content-Length": str(asset.size),
            "X-Content-Type-Options": "nosniff"
        }
    )


@router.get("/assets/{asset_id}/download")
async def download_asset(
    asset_id: str,
    if_none_match: str = Header(None),
    db: Session = Depends(get_db)
):
    """Download asset with conditional request support (304 Not Modified)."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    # Check for conditional request
    if should_return_304(if_none_match, asset.etag):
        return Response(
            status_code=304,
            headers={
                "ETag": asset.etag,
                "Cache-Control": generate_cache_control_header(asset.is_public),
            }
        )
    
    # Download file content
    content = await storage_service.download_file(asset.object_key)
    if content is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve file")
    
    return Response(
        content=content,
        media_type=asset.mime_type,
        headers={
            "ETag": asset.etag,
            "Last-Modified": get_last_modified_header(asset.updated_at),
            "Cache-Control": generate_cache_control_header(asset.is_public),
            "Content-Disposition": f"attachment; filename={asset.filename}",
            "X-Content-Type-Options": "nosniff"
        }
    )


@router.post("/assets/{asset_id}/publish")
async def publish_version(
    asset_id: str,
    db: Session = Depends(get_db)
) -> PublishResponse:
    """Create an immutable version of an asset for CDN caching."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    # Download current asset content
    content = await storage_service.download_file(asset.object_key)
    if content is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve file for versioning")
    
    # Create versioned object key
    version_key = f"versions/{asset.id}/v{asset.version}/{asset.filename}"
    
    # Upload versioned content
    success = await storage_service.upload_file(
        version_key,
        content,
        asset.mime_type
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create version")
    
    # Create AssetVersion record
    asset_version = AssetVersion(
        id=str(uuid.uuid4()),
        asset_id=asset.id,
        version_number=asset.version,
        object_key=version_key,
        etag=asset.etag
    )
    
    # Increment version number
    asset.version += 1
    
    db.add(asset_version)
    db.commit()
    db.refresh(asset_version)
    
    # Purge old version from CDN
    await cdn_service.purge_cache([
        f"{CDN_ENDPOINT}/assets/public/{asset_version.id}"
    ])
    
    return PublishResponse(
        version_id=asset_version.id,
        version_number=asset_version.version_number,
        etag=asset_version.etag,
        url=f"{CDN_ENDPOINT}/assets/public/{asset_version.id}"
    )


@router.get("/public/{version_id}")
async def get_public_version(
    version_id: str,
    if_none_match: str = Header(None),
    db: Session = Depends(get_db)
):
    """Serve immutable versioned content with aggressive caching."""
    version = db.query(AssetVersion).filter(AssetVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    
    # Check for conditional request
    if should_return_304(if_none_match, version.etag):
        return Response(
            status_code=304,
            headers={
                "ETag": version.etag,
                "Cache-Control": "public, max-age=31536000, immutable",
            }
        )
    
    # Download file content
    content = await storage_service.download_file(version.object_key)
    if content is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve file")
    
    asset = version.asset
    return Response(
        content=content,
        media_type=asset.mime_type,
        headers={
            "ETag": version.etag,
            "Last-Modified": get_last_modified_header(version.created_at),
            "Cache-Control": "public, max-age=31536000, immutable",
            "Content-Disposition": f"attachment; filename={asset.filename}",
            "X-Content-Type-Options": "nosniff",
            "X-Version-Number": str(version.version_number)
        }
    )


@router.get("/private/{token}")
async def get_private_asset(
    token: str,
    if_none_match: str = Header(None),
    db: Session = Depends(get_db)
):
    """Download private asset using access token."""
    access_token = db.query(AccessToken).filter(AccessToken.token == token).first()
    
    if not access_token or not access_token.is_valid():
        raise HTTPException(status_code=403, detail="Invalid or expired token")
    
    asset = access_token.asset
    
    # Check for conditional request
    if should_return_304(if_none_match, asset.etag):
        return Response(
            status_code=304,
            headers={
                "ETag": asset.etag,
                "Cache-Control": "private, no-store, no-cache, must-revalidate",
            }
        )
    
    # Download file content
    content = await storage_service.download_file(asset.object_key)
    if content is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve file")
    
    return Response(
        content=content,
        media_type=asset.mime_type,
        headers={
            "ETag": asset.etag,
            "Last-Modified": get_last_modified_header(asset.updated_at),
            "Cache-Control": "private, no-store, no-cache, must-revalidate",
            "Content-Disposition": f"attachment; filename={asset.filename}",
            "X-Content-Type-Options": "nosniff"
        }
    )


@router.post("/assets/{asset_id}/access-token")
async def create_access_token(
    asset_id: str,
    expiry_seconds: int = 3600,
    db: Session = Depends(get_db)
) -> AccessTokenResponse:
    """Create a time-limited access token for private asset."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    token = generate_access_token()
    expires_at = create_token_expiry(expiry_seconds)
    
    access_token = AccessToken(
        id=str(uuid.uuid4()),
        token=token,
        asset_id=asset_id,
        expires_at=expires_at
    )
    
    db.add(access_token)
    db.commit()
    db.refresh(access_token)
    
    return AccessTokenResponse.model_validate(access_token)


@router.get("/assets/{asset_id}")
async def get_asset_info(
    asset_id: str,
    db: Session = Depends(get_db)
) -> AssetResponse:
    """Get asset metadata."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    return AssetResponse.model_validate(asset)
