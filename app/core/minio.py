from minio import Minio
from minio.error import S3Error
from typing import Optional, BinaryIO
import io
from datetime import timedelta

from app.core.config import settings


class MinioClient:
    def __init__(self):
        # Construct the full endpoint with port
        endpoint = f"{settings.MINIO_ENDPOINT}"
        self.client = Minio(
            endpoint,
            access_key=settings.MINIO_ROOT_USER,
            secret_key=settings.MINIO_ROOT_PASSWORD,
            secure=settings.MINIO_SECURE
        )
        self.bucket_name = settings.MINIO_BUCKET_NAME

    async def ensure_bucket_exists(self):
        """Ensure the bucket exists, create if not"""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
        except S3Error as e:
            raise Exception(f"Error ensuring bucket exists: {e}")

    async def upload_file(
        self,
        file_data: BinaryIO,
        object_name: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[dict] = None
    ) -> str:
        """Upload a file to MinIO"""
        try:
            # Ensure bucket exists
            await self.ensure_bucket_exists()

            # Get file size
            file_data.seek(0, 2)  # Seek to end
            file_size = file_data.tell()
            file_data.seek(0)  # Reset to beginning

            # Upload file
            self.client.put_object(
                self.bucket_name,
                object_name,
                file_data,
                file_size,
                content_type=content_type,
                metadata=metadata or {}
            )

            return object_name
        except S3Error as e:
            raise Exception(f"Error uploading file: {e}")

    async def download_file(self, object_name: str) -> bytes:
        """Download a file from MinIO"""
        try:
            response = self.client.get_object(self.bucket_name, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            return data
        except S3Error as e:
            raise Exception(f"Error downloading file: {e}")

    async def get_file_url(self, object_name: str, expires: int = 3600) -> str:
        """Get a presigned URL for a file"""
        try:
            url = self.client.presigned_get_object(
                self.bucket_name,
                object_name,
                expires=timedelta(seconds=expires)
            )
            return url
        except S3Error as e:
            raise Exception(f"Error generating presigned URL: {e}")

    async def delete_file(self, object_name: str) -> bool:
        """Delete a file from MinIO"""
        try:
            self.client.remove_object(self.bucket_name, object_name)
            return True
        except S3Error as e:
            raise Exception(f"Error deleting file: {e}")

    async def file_exists(self, object_name: str) -> bool:
        """Check if a file exists in MinIO"""
        try:
            self.client.stat_object(self.bucket_name, object_name)
            return True
        except S3Error:
            return False


# Global MinIO client instance
minio_client = MinioClient()


async def get_minio() -> MinioClient:
    """Dependency to get MinIO client"""
    return minio_client 