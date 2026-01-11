import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app, get_db
from app.database import Base
from app.models.asset import Asset, AssetVersion, AccessToken
import io

# Test database
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup():
    """Clear database before each test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_upload_asset():
    """Test uploading a new asset."""
    file_content = b"test file content"
    response = client.post(
        "/assets/upload",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        params={"is_public": True}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "test.txt"
    assert data["mime_type"] == "text/plain"
    assert data["size"] == len(file_content)
    assert "etag" in data
    assert data["is_public"] is True


def test_get_asset_info():
    """Test retrieving asset information."""
    # Upload asset first
    file_content = b"test file content"
    upload_response = client.post(
        "/assets/upload",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        params={"is_public": True}
    )
    asset_id = upload_response.json()["id"]
    
    # Get asset info
    response = client.get(f"/assets/assets/{asset_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == asset_id
    assert data["filename"] == "test.txt"


def test_head_asset():
    """Test HEAD request for asset."""
    # Upload asset first
    file_content = b"test file content"
    upload_response = client.post(
        "/assets/upload",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        params={"is_public": True}
    )
    asset_id = upload_response.json()["id"]
    etag = upload_response.json()["etag"]
    
    # HEAD request
    response = client.head(f"/assets/assets/{asset_id}/download")
    assert response.status_code == 200
    assert response.headers["etag"] == etag
    assert "cache-control" in response.headers
    assert response.content == b""


def test_conditional_get_304():
    """Test conditional GET returning 304 Not Modified."""
    # Upload asset first
    file_content = b"test file content"
    upload_response = client.post(
        "/assets/upload",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        params={"is_public": True}
    )
    asset_id = upload_response.json()["id"]
    etag = upload_response.json()["etag"]
    
    # GET with matching ETag
    response = client.get(
        f"/assets/assets/{asset_id}/download",
        headers={"If-None-Match": etag}
    )
    assert response.status_code == 304
    assert response.content == b""


def test_get_asset_with_different_etag():
    """Test GET with non-matching ETag returns full content."""
    # Upload asset first
    file_content = b"test file content"
    upload_response = client.post(
        "/assets/upload",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        params={"is_public": True}
    )
    asset_id = upload_response.json()["id"]
    
    # GET with non-matching ETag
    response = client.get(
        f"/assets/assets/{asset_id}/download",
        headers={"If-None-Match": '"different-etag"'}
    )
    assert response.status_code == 200
    assert response.content is not None


def test_cache_control_headers_public():
    """Test Cache-Control headers for public assets."""
    file_content = b"test file content"
    upload_response = client.post(
        "/assets/upload",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        params={"is_public": True}
    )
    asset_id = upload_response.json()["id"]
    
    response = client.get(f"/assets/assets/{asset_id}/download")
    assert response.status_code == 200
    cache_control = response.headers.get("cache-control")
    assert "public" in cache_control


def test_cache_control_headers_private():
    """Test Cache-Control headers for private assets."""
    file_content = b"test file content"
    upload_response = client.post(
        "/assets/upload",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        params={"is_public": False}
    )
    asset_id = upload_response.json()["id"]
    
    response = client.get(f"/assets/assets/{asset_id}/download")
    assert response.status_code == 200
    cache_control = response.headers.get("cache-control")
    assert "private" in cache_control
    assert "no-store" in cache_control


def test_etag_header_present():
    """Test that ETag header is present in responses."""
    file_content = b"test file content"
    upload_response = client.post(
        "/assets/upload",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        params={"is_public": True}
    )
    asset_id = upload_response.json()["id"]
    etag = upload_response.json()["etag"]
    
    response = client.get(f"/assets/assets/{asset_id}/download")
    assert response.status_code == 200
    assert response.headers["etag"] == etag


def test_last_modified_header_present():
    """Test that Last-Modified header is present."""
    file_content = b"test file content"
    upload_response = client.post(
        "/assets/upload",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        params={"is_public": True}
    )
    asset_id = upload_response.json()["id"]
    
    response = client.get(f"/assets/assets/{asset_id}/download")
    assert response.status_code == 200
    assert "last-modified" in response.headers


def test_create_access_token():
    """Test creating an access token for private asset."""
    file_content = b"test file content"
    upload_response = client.post(
        "/assets/upload",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        params={"is_public": False}
    )
    asset_id = upload_response.json()["id"]
    
    response = client.post(
        f"/assets/assets/{asset_id}/access-token",
        params={"expiry_seconds": 3600}
    )
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert "expires_at" in data


def test_asset_not_found():
    """Test 404 for non-existent asset."""
    response = client.get("/assets/assets/nonexistent/download")
    assert response.status_code == 404


def test_upload_empty_file():
    """Test uploading empty file returns error."""
    response = client.post(
        "/assets/upload",
        files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")}
    )
    assert response.status_code == 400
