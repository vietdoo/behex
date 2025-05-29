from typing import Optional, List, BinaryIO
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import UploadFile
import uuid
import os
import json
import io

from app.repositories.file import FileRepository
from app.core.minio import MinioClient
from app.core.redis import RedisClient
from app.core.config import settings
from app.schemas.file import FileCreate, FileUpdate, FileShare
from app.models.file import File


class FileService:
    def __init__(self, db: AsyncSession):
        self.file_repo = FileRepository(db)
        self.minio_client = MinioClient()
        self.redis_client = RedisClient()

    def _generate_object_name(self, filename: str, user_id: int) -> str:
        """Generate unique object name for MinIO storage"""
        file_extension = os.path.splitext(filename)[1]
        unique_id = str(uuid.uuid4())
        return f"users/{user_id}/{unique_id}{file_extension}"

    def _get_cache_key(self, file_id: uuid.UUID) -> str:
        """Get cache key for file metadata"""
        return f"file:metadata:{file_id}"

    async def upload_file(
        self,
        file: UploadFile,
        user_id: int,
        filename: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[File]:
        """Upload a file to MinIO and create database record"""
        try:
            # Validate file size
            file_content = await file.read()
            file_size = len(file_content)
            
            if file_size > settings.MAX_FILE_SIZE_BYTES:
                return None
            
            # Validate file extension
            file_extension = os.path.splitext(file.filename)[1].lower()
            if file_extension not in settings.ALLOWED_EXTENSIONS:
                return None
            
            # Generate object name
            object_name = self._generate_object_name(file.filename, user_id)
            
            # Upload to MinIO - use BytesIO to create a file-like object from content
            file_obj = io.BytesIO(file_content)
            await self.minio_client.upload_file(
                file_obj,
                object_name,
                file.content_type or "application/octet-stream",
                metadata={
                    "original_filename": file.filename,
                    "user_id": str(user_id)
                }
            )
            
            # Create database record
            file_data = FileCreate(
                filename=filename or file.filename,
                description=description
            )
            
            db_file = await self.file_repo.create(
                file_data=file_data,
                owner_id=user_id,
                object_name=object_name,
                original_filename=file.filename,
                file_size=file_size,
                content_type=file.content_type or "application/octet-stream",
                file_extension=file_extension,
                bucket_name=settings.MINIO_BUCKET_NAME
            )
            
            # Cache file metadata
            if db_file:
                await self._cache_file_metadata(db_file)
            
            return db_file
            
        except Exception as e:
            # Clean up MinIO object if database operation fails
            if 'object_name' in locals():
                try:
                    await self.minio_client.delete_file(object_name)
                except:
                    pass
            raise e

    async def get_file(self, file_id: uuid.UUID, user_id: Optional[int] = None) -> Optional[File]:
        """Get file metadata with caching"""
        # Try to get from cache first
        cache_key = self._get_cache_key(file_id)
        cached_data = await self.redis_client.get_json(cache_key)
        
        if cached_data:
            # Verify access if user_id provided
            if user_id and cached_data.get("owner_id") != user_id and not cached_data.get("is_public"):
                return None
            return File(**cached_data)
        
        # Get from database
        db_file = await self.file_repo.get_by_id(file_id)
        if not db_file:
            return None
        
        # Verify access
        if user_id and db_file.owner_id != user_id and not db_file.is_public:
            return None
        
        # Cache the result
        await self._cache_file_metadata(db_file)
        
        return db_file

    async def download_file(self, file_id: uuid.UUID, user_id: Optional[int] = None) -> Optional[bytes]:
        """Download file content from MinIO"""
        # Get file metadata
        db_file = await self.get_file(file_id, user_id)
        if not db_file:
            return None
        
        # Download from MinIO
        try:
            file_content = await self.minio_client.download_file(db_file.object_name)
            return file_content
        except:
            return None

    async def get_file_url(self, file_id: uuid.UUID, user_id: Optional[int] = None, expires: int = 3600) -> Optional[str]:
        """Get presigned URL for direct file access"""
        # Get file metadata
        db_file = await self.get_file(file_id, user_id)
        if not db_file:
            return None
        
        # Generate presigned URL
        try:
            url = await self.minio_client.get_file_url(db_file.object_name, expires)
            return url
        except:
            return None

    async def list_user_files(self, user_id: int, skip: int = 0, limit: int = 100) -> List[File]:
        """List all files for a user"""
        return await self.file_repo.get_user_files(user_id, skip, limit)

    async def update_file(self, file_id: uuid.UUID, user_id: int, file_data: FileUpdate) -> Optional[File]:
        """Update file metadata"""
        # Verify ownership
        if not await self.file_repo.is_owner(file_id, user_id):
            return None
        
        # Update file
        updated_file = await self.file_repo.update(file_id, file_data)
        
        # Update cache
        if updated_file:
            await self._cache_file_metadata(updated_file)
        
        return updated_file

    async def delete_file(self, file_id: uuid.UUID, user_id: int) -> bool:
        """Delete file from MinIO and database"""
        # Get file metadata
        db_file = await self.file_repo.get_by_id(file_id)
        if not db_file or db_file.owner_id != user_id:
            return False
        
        # Delete from MinIO
        try:
            await self.minio_client.delete_file(db_file.object_name)
        except:
            pass  # Continue even if MinIO deletion fails
        
        # Delete from database
        deleted = await self.file_repo.delete(file_id)
        
        # Remove from cache
        if deleted:
            cache_key = self._get_cache_key(file_id)
            await self.redis_client.delete(cache_key)
        
        return deleted

    async def create_share_link(self, file_id: uuid.UUID, user_id: int) -> Optional[FileShare]:
        """Create a shareable link for a file"""
        # Verify ownership
        if not await self.file_repo.is_owner(file_id, user_id):
            return None
        
        # Create share token
        share_token = await self.file_repo.create_share_token(file_id)
        if not share_token:
            return None
        
        # Update cache
        db_file = await self.file_repo.get_by_id(file_id)
        if db_file:
            await self._cache_file_metadata(db_file)
        
        # Generate share URL
        base_url = settings.GOOGLE_REDIRECT_URI.replace("/api/v1/auth/google/callback", "")
        share_url = f"{base_url}/share/{share_token}"
        
        return FileShare(
            share_url=share_url,
            share_token=share_token
        )

    async def get_file_by_share_token(self, share_token: str) -> Optional[File]:
        """Get file by share token"""
        return await self.file_repo.get_by_share_token(share_token)

    async def revoke_share_link(self, file_id: uuid.UUID, user_id: int) -> bool:
        """Revoke share link for a file"""
        # Verify ownership
        if not await self.file_repo.is_owner(file_id, user_id):
            return False
        
        # Revoke share token
        revoked = await self.file_repo.revoke_share_token(file_id)
        
        # Update cache
        if revoked:
            db_file = await self.file_repo.get_by_id(file_id)
            if db_file:
                await self._cache_file_metadata(db_file)
        
        return revoked

    async def _cache_file_metadata(self, file: File) -> None:
        """Cache file metadata in Redis"""
        cache_key = self._get_cache_key(file.id)
        file_dict = {
            "id": file.id,
            "filename": file.filename,
            "original_filename": file.original_filename,
            "file_size": file.file_size,
            "content_type": file.content_type,
            "file_extension": file.file_extension,
            "object_name": file.object_name,
            "owner_id": file.owner_id,
            "is_public": file.is_public,
            "share_token": file.share_token,
            "description": file.description,
            "created_at": file.created_at.isoformat() if file.created_at else None,
            "updated_at": file.updated_at.isoformat() if file.updated_at else None
        }
        await self.redis_client.set_json(cache_key, file_dict, expire=3600) 