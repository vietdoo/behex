from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from enum import Enum


class FriendshipStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    BLOCKED = "blocked"


class UserSearchResult(BaseModel):
    id: int
    username: str
    full_name: Optional[str] = None
    email: str
    is_friend: bool = False
    friendship_status: Optional[FriendshipStatus] = None

    class Config:
        from_attributes = True


class FriendRequestCreate(BaseModel):
    addressee_id: int


class FriendRequestResponse(BaseModel):
    request_id: int


class FriendshipBase(BaseModel):
    id: int
    status: FriendshipStatus
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class FriendshipWithUser(FriendshipBase):
    friend: UserSearchResult

    class Config:
        from_attributes = True


class FriendRequestDetail(FriendshipBase):
    requester: UserSearchResult
    addressee: UserSearchResult

    class Config:
        from_attributes = True


class FriendsList(BaseModel):
    friends: List[UserSearchResult]
    total_count: int


class PendingRequests(BaseModel):
    sent_requests: List[FriendRequestDetail]
    received_requests: List[FriendRequestDetail]
    total_sent: int
    total_received: int


class FriendRequestAction(BaseModel):
    action: str  # "accept" or "reject" 