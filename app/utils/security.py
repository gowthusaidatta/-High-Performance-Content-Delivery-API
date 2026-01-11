import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from app.config import SECRET_KEY, TOKEN_EXPIRY_SECONDS


def generate_etag(content: bytes) -> str:
    """Generate a strong ETag using SHA-256 hash of content."""
    return f'"{hashlib.sha256(content).hexdigest()}"'


def generate_access_token() -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(32)


def create_token_expiry(seconds: int = TOKEN_EXPIRY_SECONDS) -> datetime:
    """Calculate token expiry time."""
    return datetime.utcnow() + timedelta(seconds=seconds)


def verify_token_signature(token: str, signature: str) -> bool:
    """Verify HMAC signature of token."""
    expected_signature = hmac.new(
        SECRET_KEY.encode(),
        token.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected_signature)


def create_token_signature(token: str) -> str:
    """Create HMAC signature for token."""
    return hmac.new(
        SECRET_KEY.encode(),
        token.encode(),
        hashlib.sha256
    ).hexdigest()
