from minio import Minio
from minio.error import S3Error
import io
from app.config import S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET, S3_REGION, USE_SSL


class StorageService:
    def __init__(self):
        self.client = Minio(
            S3_ENDPOINT.replace("http://", "").replace("https://", ""),
            access_key=S3_ACCESS_KEY,
            secret_key=S3_SECRET_KEY,
            secure=USE_SSL,
            region=S3_REGION
        )
        self.bucket = S3_BUCKET
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        """Create bucket if it doesn't exist."""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except S3Error as e:
            print(f"Error ensuring bucket exists: {e}")

    async def upload_file(self, object_name: str, file_content: bytes, content_type: str = "application/octet-stream") -> bool:
        """Upload file to object storage."""
        try:
            self.client.put_object(
                self.bucket,
                object_name,
                io.BytesIO(file_content),
                len(file_content),
                content_type=content_type
            )
            return True
        except S3Error as e:
            print(f"Error uploading file: {e}")
            return False

    async def download_file(self, object_name: str) -> bytes:
        """Download file from object storage."""
        try:
            response = self.client.get_object(self.bucket, object_name)
            return response.read()
        except S3Error as e:
            print(f"Error downloading file: {e}")
            return None

    async def get_signed_url(self, object_name: str, expiry_seconds: int = 3600) -> str:
        """Get signed URL for file access."""
        try:
            url = self.client.get_presigned_download_url(
                self.bucket,
                object_name,
                expires=expiry_seconds
            )
            return url
        except S3Error as e:
            print(f"Error generating signed URL: {e}")
            return None

    async def delete_file(self, object_name: str) -> bool:
        """Delete file from object storage."""
        try:
            self.client.remove_object(self.bucket, object_name)
            return True
        except S3Error as e:
            print(f"Error deleting file: {e}")
            return False


# Initialize storage service
storage_service = StorageService()
