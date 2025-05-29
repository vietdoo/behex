from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
import uuid

from app.models.file import File
from app.schemas.file import FileCreate, FileUpdate


class FileRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        file_data: FileCreate,
        owner_id: int,
        object_name: str,
        original_filename: str,
        file_size: int,
        content_type: str,
        file_extension: str,
        bucket_name: str
    ) -> File:
        """Create a new file record"""
        db_file = File(
            filename=file_data.filename,
            original_filename=original_filename,
            file_size=file_size,
            content_type=content_type,
            file_extension=file_extension,
            object_name=object_name,
            bucket_name=bucket_name,
            description=file_data.description,
            owner_id=owner_id,
            is_public=False
        )
        self.db.add(db_file)
        await self.db.commit()
        await self.db.refresh(db_file)
        return db_file

    async def get_by_id(self, file_id: uuid.UUID) -> Optional[File]:
        """Get file by ID"""
        query = select(File).filter(File.id == file_id).options(selectinload(File.owner))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_object_name(self, object_name: str) -> Optional[File]:
        """Get file by object name"""
        query = select(File).filter(File.object_name == object_name).options(selectinload(File.owner))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_share_token(self, share_token: str) -> Optional[File]:
        """Get file by share token"""
        query = select(File).filter(File.share_token == share_token).options(selectinload(File.owner))
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_user_files(self, user_id: int, skip: int = 0, limit: int = 100) -> List[File]:
        """Get all files for a user"""
        query = (
            select(File)
            .filter(File.owner_id == user_id)
            .offset(skip)
            .limit(limit)
            .order_by(File.created_at.desc())
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def update(self, file_id: uuid.UUID, file_data: FileUpdate) -> Optional[File]:
        """Update file metadata"""
        file = await self.get_by_id(file_id)
        if not file:
            return None

        update_data = file_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(file, field, value)

        await self.db.commit()
        await self.db.refresh(file)
        return file

    async def delete(self, file_id: uuid.UUID) -> bool:
        """Delete file record"""
        file = await self.get_by_id(file_id)
        if not file:
            return False

        await self.db.delete(file)
        await self.db.commit()
        return True

    async def create_share_token(self, file_id: uuid.UUID) -> Optional[str]:
        """Create a share token for a file"""
        file = await self.get_by_id(file_id)
        if not file:
            return None

        file.share_token = str(uuid.uuid4())
        file.is_public = True
        await self.db.commit()
        return file.share_token

    async def revoke_share_token(self, file_id: uuid.UUID) -> bool:
        """Revoke share token for a file"""
        file = await self.get_by_id(file_id)
        if not file:
            return False

        file.share_token = None
        file.is_public = False
        await self.db.commit()
        return True

    async def is_owner(self, file_id: uuid.UUID, user_id: int) -> bool:
        """Check if user is the owner of a file"""
        query = select(File).filter(
            and_(File.id == file_id, File.owner_id == user_id)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None 