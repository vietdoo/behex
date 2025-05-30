from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any

from app.core.database import get_db
from app.api.deps import get_current_active_user
from app.schemas.friendship import (
    UserSearchResult, FriendRequestCreate, FriendRequestResponse,
    FriendRequestAction, FriendsList, PendingRequests, FriendRequestDetail
)
from app.models.user import User as UserModel
from app.services.friendship import FriendshipService

router = APIRouter()


@router.get("/search", response_model=List[UserSearchResult])
async def search_users(
    q: str = Query(..., min_length=2, description="Search query (username, full name, or email)"),
    limit: int = Query(20, ge=1, le=50, description="Maximum number of results"),
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Search for users by username, full name, or email"""
    service = FriendshipService(db)
    return await service.search_users(q, current_user.id, limit)


@router.post("/requests", response_model=FriendRequestResponse)
async def send_friend_request(
    request_data: FriendRequestCreate,
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Send a friend request to another user"""
    service = FriendshipService(db)
    return await service.send_friend_request(current_user.id, request_data.addressee_id)


@router.put("/requests/{request_id}")
async def handle_friend_request(
    request_id: int,
    action_data: FriendRequestAction,
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Accept or reject a friend request"""
    service = FriendshipService(db)
    return await service.handle_friend_request(request_id, action_data.action, current_user.id)


@router.get("/requests", response_model=PendingRequests)
async def get_pending_requests(
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all pending friend requests (sent and received)"""
    service = FriendshipService(db)
    return await service.get_pending_requests(current_user.id)


@router.get("/", response_model=FriendsList)
async def get_friends(
    limit: int = Query(50, ge=1, le=100, description="Maximum number of friends to return"),
    offset: int = Query(0, ge=0, description="Number of friends to skip"),
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get list of current user's friends with pagination"""
    service = FriendshipService(db)
    return await service.get_friends_list(current_user.id, limit, offset)


@router.delete("/unfriend/{friend_id}")
async def unfriend_user(
    friend_id: int,
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove friendship with another user"""
    service = FriendshipService(db)
    return await service.unfriend_user(current_user.id, friend_id)


@router.post("/block/{user_id}")
async def block_user(
    user_id: int,
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Block a user (removes any existing friendship)"""
    service = FriendshipService(db)
    return await service.block_user(current_user.id, user_id)


@router.delete("/block/{user_id}")
async def unblock_user(
    user_id: int,
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Unblock a user"""
    service = FriendshipService(db)
    return await service.unblock_user(current_user.id, user_id) 