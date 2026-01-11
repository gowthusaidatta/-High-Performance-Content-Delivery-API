from datetime import datetime
from typing import Optional, Tuple


def generate_cache_control_header(
    is_public: bool,
    is_immutable: bool = False,
    max_age: int = 60,
    s_maxage: int = 3600
) -> str:
    """Generate appropriate Cache-Control header based on content type."""
    if is_public:
        if is_immutable:
            return "public, max-age=31536000, immutable"
        else:
            return f"public, s-maxage={s_maxage}, max-age={max_age}"
    else:
        return "private, no-store, no-cache, must-revalidate"


def should_return_304(
    client_etag: Optional[str],
    server_etag: str
) -> bool:
    """Determine if 304 Not Modified should be returned."""
    if not client_etag:
        return False
    return client_etag == server_etag or client_etag.strip('"') == server_etag.strip('"')


def get_last_modified_header(dt: datetime) -> str:
    """Format datetime as RFC 2822 Last-Modified header."""
    return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")
