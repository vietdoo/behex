from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, and_, func, select
from sqlalchemy.orm import selectinload
from typing import List, Optional, Tuple

from app.models.friendship import Friendship
from app.models.user import User
from app.schemas.friendship import FriendshipStatus


class FriendshipRepository:
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def search_users(self, query: str, current_user_id: int, limit: int = 20) -> List[User]:
        """Search users by username, full_name, or email"""
        stmt = select(User).where(
            and_(
                User.id != current_user_id,  # Exclude current user
                User.is_active == True,
                or_(
                    User.username.ilike(f"%{query}%"),
                    User.full_name.ilike(f"%{query}%"),
                    User.email.ilike(f"%{query}%")
                )
            )
        ).limit(limit)
        
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def get_friendship_status(self, user1_id: int, user2_id: int) -> Optional[Friendship]:
        """Get friendship status between two users"""
        stmt = select(Friendship).where(
            or_(
                and_(Friendship.requester_id == user1_id, Friendship.addressee_id == user2_id),
                and_(Friendship.requester_id == user2_id, Friendship.addressee_id == user1_id)
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def create_friend_request(self, requester_id: int, addressee_id: int) -> Friendship:
        """Create a new friend request"""
        friendship = Friendship(
            requester_id=requester_id,
            addressee_id=addressee_id,
            status=FriendshipStatus.PENDING
        )
        self.db.add(friendship)
        await self.db.commit()
        await self.db.refresh(friendship)
        return friendship
    
    async def get_friend_request(self, request_id: int) -> Optional[Friendship]:
        """Get a specific friend request by ID"""
        stmt = select(Friendship).where(Friendship.id == request_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def accept_friend_request(self, request_id: int, user_id: int) -> Optional[Friendship]:
        """Accept a friend request (only the addressee can accept)"""
        stmt = select(Friendship).where(
            and_(
                Friendship.id == request_id,
                Friendship.addressee_id == user_id,
                Friendship.status == FriendshipStatus.PENDING
            )
        )
        result = await self.db.execute(stmt)
        friendship = result.scalar_one_or_none()
        
        if friendship:
            friendship.status = FriendshipStatus.ACCEPTED
            await self.db.commit()
            await self.db.refresh(friendship)
        
        return friendship
    
    async def reject_friend_request(self, request_id: int, user_id: int) -> bool:
        """Reject/delete a friend request"""
        stmt = select(Friendship).where(
            and_(
                Friendship.id == request_id,
                or_(
                    Friendship.addressee_id == user_id,  # Addressee can reject
                    Friendship.requester_id == user_id   # Requester can cancel
                ),
                Friendship.status == FriendshipStatus.PENDING
            )
        )
        result = await self.db.execute(stmt)
        friendship = result.scalar_one_or_none()
        
        if friendship:
            await self.db.delete(friendship)
            await self.db.commit()
            return True
        
        return False
    
    async def unfriend(self, user1_id: int, user2_id: int) -> bool:
        """Remove friendship between two users"""
        stmt = select(Friendship).where(
            and_(
                or_(
                    and_(Friendship.requester_id == user1_id, Friendship.addressee_id == user2_id),
                    and_(Friendship.requester_id == user2_id, Friendship.addressee_id == user1_id)
                ),
                Friendship.status == FriendshipStatus.ACCEPTED
            )
        )
        result = await self.db.execute(stmt)
        friendship = result.scalar_one_or_none()
        
        if friendship:
            await self.db.delete(friendship)
            await self.db.commit()
            return True
        
        return False
    
    async def get_friends(self, user_id: int, limit: int = 50, offset: int = 0) -> Tuple[List[User], int]:
        """Get list of friends for a user with pagination"""
        # Query for accepted friendships where user is either requester or addressee
        friends_stmt = select(User).join(
            Friendship,
            or_(
                and_(Friendship.requester_id == user_id, Friendship.addressee_id == User.id),
                and_(Friendship.addressee_id == user_id, Friendship.requester_id == User.id)
            )
        ).where(
            Friendship.status == FriendshipStatus.ACCEPTED
        )
        
        # Get total count
        count_stmt = select(func.count()).select_from(friends_stmt.subquery())
        count_result = await self.db.execute(count_stmt)
        total_count = count_result.scalar()
        
        # Get paginated results
        friends_stmt = friends_stmt.offset(offset).limit(limit)
        friends_result = await self.db.execute(friends_stmt)
        friends = friends_result.scalars().all()
        
        return friends, total_count
    
    async def get_pending_requests(self, user_id: int) -> Tuple[List[Friendship], List[Friendship]]:
        """Get sent and received pending friend requests"""
        # Sent requests with loaded relationships
        sent_stmt = select(Friendship).options(
            selectinload(Friendship.requester),
            selectinload(Friendship.addressee)
        ).where(
            and_(
                Friendship.requester_id == user_id,
                Friendship.status == FriendshipStatus.PENDING
            )
        )
        sent_result = await self.db.execute(sent_stmt)
        sent_requests = sent_result.scalars().all()
        
        # Received requests with loaded relationships
        received_stmt = select(Friendship).options(
            selectinload(Friendship.requester),
            selectinload(Friendship.addressee)
        ).where(
            and_(
                Friendship.addressee_id == user_id,
                Friendship.status == FriendshipStatus.PENDING
            )
        )
        received_result = await self.db.execute(received_stmt)
        received_requests = received_result.scalars().all()
        
        return sent_requests, received_requests
    
    async def block_user(self, blocker_id: int, blocked_id: int) -> Friendship:
        """Block a user (remove any existing friendship and create block record)"""
        # Remove any existing friendship
        existing = await self.get_friendship_status(blocker_id, blocked_id)
        if existing:
            await self.db.delete(existing)
        
        # Create block record
        block = Friendship(
            requester_id=blocker_id,
            addressee_id=blocked_id,
            status=FriendshipStatus.BLOCKED
        )
        self.db.add(block)
        await self.db.commit()
        await self.db.refresh(block)
        return block
    
    async def unblock_user(self, blocker_id: int, blocked_id: int) -> bool:
        """Unblock a user"""
        stmt = select(Friendship).where(
            and_(
                Friendship.requester_id == blocker_id,
                Friendship.addressee_id == blocked_id,
                Friendship.status == FriendshipStatus.BLOCKED
            )
        )
        result = await self.db.execute(stmt)
        block = result.scalar_one_or_none()
        
        if block:
            await self.db.delete(block)
            await self.db.commit()
            return True
        
        return False 