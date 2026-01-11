import os
from dotenv import load_dotenv

load_dotenv()

# Database Configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@localhost:5432/content_delivery"
)

# S3/MinIO Configuration
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minioadmin")
S3_BUCKET = os.getenv("S3_BUCKET", "content-delivery")
S3_REGION = os.getenv("S3_REGION", "us-east-1")
USE_SSL = os.getenv("S3_USE_SSL", "false").lower() == "true"

# CDN Configuration
CDN_ENDPOINT = os.getenv("CDN_ENDPOINT", "http://localhost:8000")
CLOUDFLARE_API_KEY = os.getenv("CLOUDFLARE_API_KEY", "")
CLOUDFLARE_ZONE_ID = os.getenv("CLOUDFLARE_ZONE_ID", "")
CDN_PURGE_ENABLED = os.getenv("CDN_PURGE_ENABLED", "false").lower() == "true"

# Security Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
TOKEN_EXPIRY_SECONDS = int(os.getenv("TOKEN_EXPIRY_SECONDS", "3600"))
ALLOWED_CDN_IPS = os.getenv("ALLOWED_CDN_IPS", "").split(",") if os.getenv("ALLOWED_CDN_IPS") else []

# Server Configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
