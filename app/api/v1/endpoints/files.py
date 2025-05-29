from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File as FastAPIFile, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import io
import uuid

from app.core.database import get_db
from app.api.deps import get_current_active_user, get_optional_current_user
from app.schemas.file import File, FileCreate, FileUpdate, FileShare
from app.schemas.user import User
from app.services.file import FileService

router = APIRouter()


@router.post("/upload", response_model=File, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = FastAPIFile(...),
    filename: Optional[str] = None,
    description: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload a new file"""
    file_service = FileService(db)
    
    uploaded_file = await file_service.upload_file(
        file=file,
        user_id=current_user.id,
        filename=filename,
        description=description
    )
    
    if not uploaded_file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File upload failed. Check file size and format."
        )
    
    return uploaded_file


@router.get("/", response_model=List[File])
async def list_files(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List current user's files"""
    file_service = FileService(db)
    files = await file_service.list_user_files(current_user.id, skip, limit)
    return files


@router.get("/{file_id}", response_model=File)
async def get_file(
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get file metadata"""
    file_service = FileService(db)
    file = await file_service.get_file(file_id, current_user.id)
    
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    return file


@router.get("/{file_id}/download")
async def download_file(
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Download file content"""
    file_service = FileService(db)
    
    # Get file metadata
    file = await file_service.get_file(file_id, current_user.id)
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Download file content
    file_content = await file_service.download_file(file_id, current_user.id)
    if not file_content:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download file"
        )
    
    # Return as streaming response
    return StreamingResponse(
        io.BytesIO(file_content),
        media_type=file.content_type,
        headers={"Content-Disposition": f"attachment; filename={file.original_filename}"}
    )


@router.get("/{file_id}/url")
async def get_file_url(
    file_id: uuid.UUID,
    expires: int = Query(3600, ge=60, le=86400),  # 1 minute to 24 hours
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get presigned URL for direct file access"""
    file_service = FileService(db)
    url = await file_service.get_file_url(file_id, current_user.id, expires)
    
    if not url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    return {"url": url, "expires_in": expires}


@router.put("/{file_id}", response_model=File)
async def update_file(
    file_id: uuid.UUID,
    file_update: FileUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update file metadata"""
    file_service = FileService(db)
    updated_file = await file_service.update_file(file_id, current_user.id, file_update)
    
    if not updated_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    return updated_file


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete file"""
    file_service = FileService(db)
    deleted = await file_service.delete_file(file_id, current_user.id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    return None


@router.post("/{file_id}/share", response_model=FileShare)
async def create_share_link(
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a shareable link for a file"""
    file_service = FileService(db)
    share_link = await file_service.create_share_link(file_id, current_user.id)
    
    if not share_link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    return share_link


@router.delete("/{file_id}/share", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_share_link(
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Revoke share link for a file"""
    file_service = FileService(db)
    revoked = await file_service.revoke_share_link(file_id, current_user.id)
    
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    return None


@router.get("/share/{share_token}")
async def download_shared_file(
    share_token: str,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Download file using share token"""
    file_service = FileService(db)
    
    # Get file by share token
    file = await file_service.get_file_by_share_token(share_token)
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shared file not found or link expired"
        )
    
    # Download file content
    file_content = await file_service.download_file(file.id)
    if not file_content:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download file"
        )
    
    # Return as streaming response
    return StreamingResponse(
        io.BytesIO(file_content),
        media_type=file.content_type,
        headers={"Content-Disposition": f"attachment; filename={file.original_filename}"}
    ) 
 