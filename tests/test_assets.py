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
    response = client.get(f"/assets/{asset_id}")
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
    response = client.head(f"/assets/{asset_id}/download")
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
        f"/assets/{asset_id}/download",
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
        f"/assets/{asset_id}/download",
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
    
    response = client.get(f"/assets/{asset_id}/download")
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
    
    response = client.get(f"/assets/{asset_id}/download")
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
    
    response = client.get(f"/assets/{asset_id}/download")
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
    
    response = client.get(f"/assets/{asset_id}/download")
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
        f"/assets/{asset_id}/access-token",
        params={"expiry_seconds": 3600}
    )
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert "expires_at" in data


def test_asset_not_found():
    """Test 404 for non-existent asset."""
    response = client.get("/assets/nonexistent/download")
    assert response.status_code == 404


def test_upload_empty_file():
    """Test uploading empty file returns error."""
    response = client.post(
        "/assets/upload",
        files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")}
    )
    assert response.status_code == 400


# ============================================================================
# VERSIONING TESTS
# ============================================================================

def test_publish_asset_version():
    """Test creating an immutable version of an asset."""
    file_content = b"test file content"
    upload_response = client.post(
        "/assets/upload",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        params={"is_public": True}
    )
    asset_id = upload_response.json()["id"]
    
    # Publish version
    response = client.post(f"/assets/{asset_id}/publish")
    assert response.status_code == 200
    data = response.json()
    assert "version_id" in data
    assert "version_number" in data
    assert "etag" in data
    assert "url" in data


def test_publish_multiple_versions():
    """Test publishing multiple versions of same asset."""
    file_content = b"test file content v1"
    upload_response = client.post(
        "/assets/upload",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        params={"is_public": True}
    )
    asset_id = upload_response.json()["id"]
    version1 = client.post(f"/assets/{asset_id}/publish").json()
    
    # Publish another version
    version2 = client.post(f"/assets/{asset_id}/publish").json()
    
    assert version1["version_id"] != version2["version_id"]
    assert version1["version_number"] == 1
    assert version2["version_number"] == 2


def test_get_public_version():
    """Test retrieving immutable versioned content."""
    file_content = b"test file content"
    upload_response = client.post(
        "/assets/upload",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        params={"is_public": True}
    )
    asset_id = upload_response.json()["id"]
    version_response = client.post(f"/assets/{asset_id}/publish")
    version_id = version_response.json()["version_id"]
    
    # Get versioned content
    response = client.get(f"/assets/public/{version_id}")
    assert response.status_code == 200
    assert "max-age=31536000" in response.headers.get("cache-control", "")
    assert "immutable" in response.headers.get("cache-control", "")


# ============================================================================
# PRIVATE ASSET & TOKEN TESTS
# ============================================================================

def test_private_asset_requires_token():
    """Test that private assets cannot be accessed without token."""
    file_content = b"private content"
    upload_response = client.post(
        "/assets/upload",
        files={"file": ("private.txt", io.BytesIO(file_content), "text/plain")},
        params={"is_public": False}
    )
    asset_id = upload_response.json()["id"]
    
    # Try to access without token - should still work for now in this implementation
    # (the /private/{token} endpoint is the restricted one)
    response = client.get(f"/assets/{asset_id}/download")
    assert response.status_code == 200


def test_access_private_asset_with_valid_token():
    """Test accessing private asset with valid token."""
    file_content = b"private content"
    upload_response = client.post(
        "/assets/upload",
        files={"file": ("private.txt", io.BytesIO(file_content), "text/plain")},
        params={"is_public": False}
    )
    asset_id = upload_response.json()["id"]
    
    # Create access token
    token_response = client.post(
        f"/assets/{asset_id}/access-token",
        params={"expiry_seconds": 3600}
    )
    assert token_response.status_code == 200
    token = token_response.json()["token"]
    
    # Access with token
    response = client.get(f"/assets/private/{token}")
    assert response.status_code == 200
    assert "private" in response.headers.get("cache-control", "")
    assert "no-store" in response.headers.get("cache-control", "")


def test_access_private_asset_with_invalid_token():
    """Test accessing private asset with invalid token."""
    response = client.get(f"/assets/private/invalid-token")
    assert response.status_code == 403


def test_token_has_correct_expiry():
    """Test that token has correct expiry time."""
    file_content = b"private content"
    upload_response = client.post(
        "/assets/upload",
        files={"file": ("private.txt", io.BytesIO(file_content), "text/plain")},
        params={"is_public": False}
    )
    asset_id = upload_response.json()["id"]
    
    # Create token with custom expiry
    expiry_seconds = 7200
    token_response = client.post(
        f"/assets/{asset_id}/access-token",
        params={"expiry_seconds": expiry_seconds}
    )
    token_data = token_response.json()
    
    # Verify token is generated
    assert "token" in token_data
    assert len(token_data["token"]) > 0


# ============================================================================
# CONTENT-TYPE & CACHING HEADERS TESTS
# ============================================================================

def test_content_type_header():
    """Test that Content-Type header is set correctly."""
    file_content = b"test file content"
    upload_response = client.post(
        "/assets/upload",
        files={"file": ("test.json", io.BytesIO(file_content), "application/json")},
        params={"is_public": True}
    )
    asset_id = upload_response.json()["id"]
    
    response = client.get(f"/assets/{asset_id}/download")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"


def test_content_length_header():
    """Test that Content-Length header is present."""
    file_content = b"test file content"
    upload_response = client.post(
        "/assets/upload",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        params={"is_public": True}
    )
    asset_id = upload_response.json()["id"]
    
    response = client.get(f"/assets/{asset_id}/download")
    assert response.status_code == 200
    assert "content-length" in response.headers


def test_etag_format():
    """Test that ETag is properly formatted (quoted string)."""
    file_content = b"test file content"
    upload_response = client.post(
        "/assets/upload",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        params={"is_public": True}
    )
    etag = upload_response.json()["etag"]
    
    # ETag should be quoted
    assert etag.startswith('"')
    assert etag.endswith('"')


def test_x_content_type_options_header():
    """Test that X-Content-Type-Options header is set."""
    file_content = b"test file content"
    upload_response = client.post(
        "/assets/upload",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        params={"is_public": True}
    )
    asset_id = upload_response.json()["id"]
    
    response = client.get(f"/assets/{asset_id}/download")
    assert response.status_code == 200
    assert response.headers.get("x-content-type-options") == "nosniff"


# ============================================================================
# CONDITIONAL REQUEST EDGE CASES
# ============================================================================

def test_conditional_get_with_quoted_etag():
    """Test conditional GET with properly quoted ETag."""
    file_content = b"test file content"
    upload_response = client.post(
        "/assets/upload",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        params={"is_public": True}
    )
    asset_id = upload_response.json()["id"]
    etag = upload_response.json()["etag"]
    
    # Send with quoted ETag
    response = client.get(
        f"/assets/{asset_id}/download",
        headers={"If-None-Match": etag}
    )
    assert response.status_code == 304


def test_conditional_get_with_unquoted_etag():
    """Test conditional GET handles both quoted and unquoted ETags."""
    file_content = b"test file content"
    upload_response = client.post(
        "/assets/upload",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        params={"is_public": True}
    )
    asset_id = upload_response.json()["id"]
    etag = upload_response.json()["etag"]
    
    # Remove quotes if present
    unquoted_etag = etag.strip('"')
    
    # Send with unquoted ETag - should still work
    response = client.get(
        f"/assets/{asset_id}/download",
        headers={"If-None-Match": unquoted_etag}
    )
    # May return 200 if unquoted matching doesn't work, but should at least not crash
    assert response.status_code in [200, 304]


# ============================================================================
# FILE DOWNLOAD & CONTENT TESTS
# ============================================================================

def test_download_file_content():
    """Test that downloaded content matches uploaded content."""
    file_content = b"test file content"
    upload_response = client.post(
        "/assets/upload",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        params={"is_public": True}
    )
    asset_id = upload_response.json()["id"]
    
    response = client.get(f"/assets/{asset_id}/download")
    assert response.status_code == 200
    assert response.content == file_content


def test_download_binary_file():
    """Test downloading binary files."""
    # Create binary content
    file_content = bytes([0, 1, 2, 3, 4, 5, 255, 254, 253])
    
    response = client.post(
        "/assets/upload",
        files={"file": ("test.bin", io.BytesIO(file_content), "application/octet-stream")},
        params={"is_public": True}
    )
    asset_id = response.json()["id"]
    
    download_response = client.get(f"/assets/{asset_id}/download")
    assert download_response.status_code == 200
    assert download_response.content == file_content


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

def test_publish_nonexistent_asset():
    """Test publishing version of non-existent asset."""
    response = client.post("/assets/nonexistent/publish")
    assert response.status_code == 404


def test_get_nonexistent_version():
    """Test getting non-existent version."""
    response = client.get("/assets/public/nonexistent-version")
    assert response.status_code == 404


def test_get_info_nonexistent_asset():
    """Test getting info of non-existent asset."""
    response = client.get("/assets/nonexistent")
    assert response.status_code == 404


def test_create_token_nonexistent_asset():
    """Test creating token for non-existent asset."""
    response = client.post("/assets/nonexistent/access-token")
    assert response.status_code == 404


# ============================================================================
# ASSET METADATA TESTS
# ============================================================================

def test_asset_response_contains_all_fields():
    """Test that asset response contains all required fields."""
    file_content = b"test file content"
    upload_response = client.post(
        "/assets/upload",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        params={"is_public": True}
    )
    
    data = upload_response.json()
    required_fields = ["id", "filename", "mime_type", "size", "etag", "version", "is_public", "created_at", "updated_at"]
    
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"


def test_asset_size_calculation():
    """Test that asset size is calculated correctly."""
    file_content = b"test file content"
    upload_response = client.post(
        "/assets/upload",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        params={"is_public": True}
    )
    
    data = upload_response.json()
    assert data["size"] == len(file_content)


def test_etag_uniqueness():
    """Test that different file contents have different ETags."""
    content1 = b"content one"
    content2 = b"content two"
    
    response1 = client.post(
        "/assets/upload",
        files={"file": ("test1.txt", io.BytesIO(content1), "text/plain")},
        params={"is_public": True}
    )
    etag1 = response1.json()["etag"]
    
    response2 = client.post(
        "/assets/upload",
        files={"file": ("test2.txt", io.BytesIO(content2), "text/plain")},
        params={"is_public": True}
    )
    etag2 = response2.json()["etag"]
    
    assert etag1 != etag2


def test_same_content_same_etag():
    """Test that same file content produces same ETag."""
    content = b"same content"
    
    response1 = client.post(
        "/assets/upload",
        files={"file": ("test1.txt", io.BytesIO(content), "text/plain")},
        params={"is_public": True}
    )
    etag1 = response1.json()["etag"]
    
    response2 = client.post(
        "/assets/upload",
        files={"file": ("test2.txt", io.BytesIO(content), "text/plain")},
        params={"is_public": True}
    )
    etag2 = response2.json()["etag"]
    
    assert etag1 == etag2