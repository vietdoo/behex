from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    SYSTEM = "system"


class ConversationType(str, Enum):
    PRIVATE = "private"
    GROUP = "group"


class WebSocketMessageType(str, Enum):
    MESSAGE = "message"
    TYPING = "typing"
    READ_RECEIPT = "read_receipt"
    USER_ONLINE = "user_online"
    USER_OFFLINE = "user_offline"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"


# Base User Schema for Chat
class ChatUser(BaseModel):
    id: int
    username: str
    full_name: Optional[str] = None
    
    class Config:
        from_attributes = True


# Message Schemas
class MessageCreate(BaseModel):
    conversation_id: int
    content: str
    message_type: MessageType = MessageType.TEXT


class MessageUpdate(BaseModel):
    content: str


class MessageBase(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    content: str
    message_type: MessageType
    is_edited: bool = False
    is_deleted: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class Message(MessageBase):
    sender: ChatUser


class MessageList(BaseModel):
    messages: List[Message]
    total_count: int
    has_more: bool = False


# Conversation Schemas
class ConversationCreate(BaseModel):
    participant_ids: List[int]
    type: ConversationType = ConversationType.PRIVATE
    name: Optional[str] = None


class ConversationParticipant(BaseModel):
    id: int
    user_id: int
    joined_at: datetime
    last_read_at: Optional[datetime] = None
    is_active: bool = True
    user: ChatUser
    
    class Config:
        from_attributes = True


class ConversationBase(BaseModel):
    id: int
    type: ConversationType
    name: Optional[str] = None
    created_by: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_message_at: datetime
    
    class Config:
        from_attributes = True


class Conversation(ConversationBase):
    participants: List[ConversationParticipant]
    last_message: Optional[Message] = None
    unread_count: int = 0


class ConversationList(BaseModel):
    conversations: List[Conversation]
    total_count: int


# WebSocket Message Schemas
class WebSocketMessage(BaseModel):
    type: WebSocketMessageType
    data: Dict[str, Any] = {}
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class IncomingMessage(BaseModel):
    type: WebSocketMessageType
    conversation_id: Optional[int] = None
    content: Optional[str] = None
    message_type: MessageType = MessageType.TEXT


class OutgoingMessage(BaseModel):
    type: WebSocketMessageType
    conversation_id: Optional[int] = None
    message: Optional[Message] = None
    user: Optional[ChatUser] = None
    data: Dict[str, Any] = {}
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Typing Indicator
class TypingIndicator(BaseModel):
    conversation_id: int
    user_id: int
    is_typing: bool


# Read Receipt
class ReadReceipt(BaseModel):
    conversation_id: int
    message_id: int
    user_id: int
    read_at: datetime = Field(default_factory=datetime.utcnow)


# Online Status
class UserStatus(BaseModel):
    user_id: int
    is_online: bool
    last_seen: Optional[datetime] = None


# Error Response
class ChatError(BaseModel):
    message: str
    code: Optional[str] = None 