from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional

from app.core.database import get_db
from app.api.deps import get_current_active_user
from app.schemas.chat import (
    ConversationCreate, Conversation, ConversationList, MessageCreate,
    Message, MessageList, MessageUpdate
)
from app.models.user import User as UserModel
from app.services.chat import ChatService

router = APIRouter()


@router.post("/conversations", response_model=Conversation)
async def create_conversation(
    conversation_data: ConversationCreate,
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new conversation"""
    service = ChatService(db)
    return await service.create_conversation(current_user.id, conversation_data)


@router.get("/conversations", response_model=ConversationList)
async def get_conversations(
    limit: int = Query(20, ge=1, le=50, description="Maximum number of conversations to return"),
    offset: int = Query(0, ge=0, description="Number of conversations to skip"),
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's conversations with pagination"""
    service = ChatService(db)
    return await service.get_user_conversations(current_user.id, limit, offset)


@router.get("/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(
    conversation_id: int,
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific conversation"""
    service = ChatService(db)
    return await service.get_conversation(conversation_id, current_user.id)


@router.get("/conversations/{conversation_id}/messages", response_model=MessageList)
async def get_conversation_messages(
    conversation_id: int,
    limit: int = Query(50, ge=1, le=100, description="Maximum number of messages to return"),
    before_message_id: Optional[int] = Query(None, description="Get messages before this message ID"),
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get messages for a conversation with pagination"""
    service = ChatService(db)
    return await service.get_conversation_messages(
        conversation_id, current_user.id, limit, before_message_id
    )


@router.post("/messages", response_model=Message)
async def send_message(
    message_data: MessageCreate,
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Send a message in a conversation"""
    service = ChatService(db)
    return await service.send_message(current_user.id, message_data)


@router.put("/messages/{message_id}", response_model=Message)
async def update_message(
    message_id: int,
    update_data: MessageUpdate,
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a message"""
    service = ChatService(db)
    return await service.update_message(message_id, current_user.id, update_data)


@router.delete("/messages/{message_id}")
async def delete_message(
    message_id: int,
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a message"""
    service = ChatService(db)
    return await service.delete_message(message_id, current_user.id)


@router.post("/conversations/{conversation_id}/read")
async def mark_conversation_as_read(
    conversation_id: int,
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark conversation as read"""
    service = ChatService(db)
    return await service.mark_conversation_as_read(conversation_id, current_user.id)


@router.post("/conversations/{conversation_id}/join")
async def join_conversation_room(
    conversation_id: int,
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Join conversation room for WebSocket updates"""
    service = ChatService(db)
    await service.join_conversation_room(current_user.id, conversation_id)
    return {"message": "Joined conversation room"}


@router.post("/conversations/{conversation_id}/leave")
async def leave_conversation_room(
    conversation_id: int,
    current_user: UserModel = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Leave conversation room"""
    service = ChatService(db)
    await service.leave_conversation_room(current_user.id, conversation_id)
    return {"message": "Left conversation room"} 