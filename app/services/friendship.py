from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict, Any
from fastapi import HTTPException, status

from app.repositories.friendship import FriendshipRepository
from app.schemas.friendship import (
    UserSearchResult, FriendsList, PendingRequests, FriendRequestDetail,
    FriendshipStatus, FriendRequestResponse
)
from app.models.user import User
from app.models.friendship import Friendship


class FriendshipService:
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = FriendshipRepository(db)
    
    async def search_users(self, query: str, current_user_id: int, limit: int = 20) -> List[UserSearchResult]:
        """Search users and include friendship status"""
        if not query or len(query.strip()) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Search query must be at least 2 characters long"
            )
        
        users = await self.repo.search_users(query.strip(), current_user_id, limit)
        results = []
        
        for user in users:
            friendship = await self.repo.get_friendship_status(current_user_id, user.id)
            
            is_friend = False
            friendship_status = None
            
            if friendship:
                friendship_status = FriendshipStatus(friendship.status)
                is_friend = friendship_status == FriendshipStatus.ACCEPTED
            
            user_result = UserSearchResult(
                id=user.id,
                username=user.username,
                full_name=user.full_name,
                email=user.email,
                is_friend=is_friend,
                friendship_status=friendship_status
            )
            results.append(user_result)
        
        return results
    
    async def send_friend_request(self, requester_id: int, addressee_id: int) -> FriendRequestResponse:
        """Send a friend request"""
        if requester_id == addressee_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot send friend request to yourself"
            )
        
        # Check if addressee exists
        stmt = select(User).where(User.id == addressee_id)
        result = await self.db.execute(stmt)
        addressee = result.scalar_one_or_none()
        
        if not addressee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check if relationship already exists
        existing_friendship = await self.repo.get_friendship_status(requester_id, addressee_id)
        if existing_friendship:
            if existing_friendship.status == FriendshipStatus.PENDING:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Friend request already sent"
                )
            elif existing_friendship.status == FriendshipStatus.ACCEPTED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="You are already friends with this user"
                )
            elif existing_friendship.status == FriendshipStatus.BLOCKED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot send friend request to this user"
                )
        
        # Create friend request
        friendship = await self.repo.create_friend_request(requester_id, addressee_id)
        return FriendRequestResponse(request_id=friendship.id)
    
    async def handle_friend_request(self, request_id: int, action: str, user_id: int) -> Dict[str, str]:
        """Accept or reject a friend request"""
        if action not in ["accept", "reject"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Action must be 'accept' or 'reject'"
            )
        
        if action == "accept":
            friendship = await self.repo.accept_friend_request(request_id, user_id)
            if not friendship:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Friend request not found or you don't have permission to accept it"
                )
            return {"message": "Friend request accepted successfully"}
        
        else:  # reject
            success = await self.repo.reject_friend_request(request_id, user_id)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Friend request not found or you don't have permission to reject it"
                )
            return {"message": "Friend request rejected successfully"}
    
    async def unfriend_user(self, current_user_id: int, friend_id: int) -> Dict[str, str]:
        """Remove friendship with another user"""
        if current_user_id == friend_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot unfriend yourself"
            )
        
        success = await self.repo.unfriend(current_user_id, friend_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Friendship not found"
            )
        
        return {"message": "Unfriended successfully"}
    
    async def get_friends_list(self, user_id: int, limit: int = 50, offset: int = 0) -> FriendsList:
        """Get list of user's friends"""
        friends, total_count = await self.repo.get_friends(user_id, limit, offset)
        
        friends_list = [
            UserSearchResult(
                id=friend.id,
                username=friend.username,
                full_name=friend.full_name,
                email=friend.email,
                is_friend=True,
                friendship_status=FriendshipStatus.ACCEPTED
            )
            for friend in friends
        ]
        
        return FriendsList(friends=friends_list, total_count=total_count)
    
    async def get_pending_requests(self, user_id: int) -> PendingRequests:
        """Get pending friend requests (sent and received)"""
        sent_requests, received_requests = await self.repo.get_pending_requests(user_id)
        
        # Convert to response format
        sent_list = []
        for req in sent_requests:
            sent_list.append(
                FriendRequestDetail(
                    id=req.id,
                    status=FriendshipStatus(req.status),
                    created_at=req.created_at,
                    updated_at=req.updated_at,
                    requester=UserSearchResult(
                        id=req.requester.id,
                        username=req.requester.username,
                        full_name=req.requester.full_name,
                        email=req.requester.email
                    ),
                    addressee=UserSearchResult(
                        id=req.addressee.id,
                        username=req.addressee.username,
                        full_name=req.addressee.full_name,
                        email=req.addressee.email
                    )
                )
            )
        
        received_list = []
        for req in received_requests:
            received_list.append(
                FriendRequestDetail(
                    id=req.id,
                    status=FriendshipStatus(req.status),
                    created_at=req.created_at,
                    updated_at=req.updated_at,
                    requester=UserSearchResult(
                        id=req.requester.id,
                        username=req.requester.username,
                        full_name=req.requester.full_name,
                        email=req.requester.email
                    ),
                    addressee=UserSearchResult(
                        id=req.addressee.id,
                        username=req.addressee.username,
                        full_name=req.addressee.full_name,
                        email=req.addressee.email
                    )
                )
            )
        
        return PendingRequests(
            sent_requests=sent_list,
            received_requests=received_list,
            total_sent=len(sent_list),
            total_received=len(received_list)
        )
    
    async def block_user(self, blocker_id: int, blocked_id: int) -> Dict[str, str]:
        """Block a user"""
        if blocker_id == blocked_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot block yourself"
            )
        
        # Check if user exists
        stmt = select(User).where(User.id == blocked_id)
        result = await self.db.execute(stmt)
        blocked_user = result.scalar_one_or_none()
        
        if not blocked_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        await self.repo.block_user(blocker_id, blocked_id)
        return {"message": "User blocked successfully"}
    
    async def unblock_user(self, blocker_id: int, blocked_id: int) -> Dict[str, str]:
        """Unblock a user"""
        success = await self.repo.unblock_user(blocker_id, blocked_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Block relationship not found"
            )
        
        return {"message": "User unblocked successfully"} 