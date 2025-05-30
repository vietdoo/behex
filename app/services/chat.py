from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict, Any, Optional, Tuple
from fastapi import HTTPException, status

from app.repositories.chat import ChatRepository
from app.repositories.friendship import FriendshipRepository
from app.schemas.chat import (
    ConversationCreate, Conversation, ConversationList, MessageCreate, 
    Message, MessageList, MessageUpdate, ConversationType, ChatUser
)
from app.schemas.friendship import FriendshipStatus
from app.models.user import User
from app.core.websocket import connection_manager


class ChatService:
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.chat_repo = ChatRepository(db)
        self.friendship_repo = FriendshipRepository(db)
    
    async def create_conversation(self, creator_id: int, conversation_data: ConversationCreate) -> Conversation:
        """Create a new conversation"""
        # Validate participants exist and are friends
        if conversation_data.type == ConversationType.PRIVATE:
            if len(conversation_data.participant_ids) != 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Private conversations must have exactly one other participant"
                )
            
            other_user_id = conversation_data.participant_ids[0]
            
            # Check if users are friends
            friendship = await self.friendship_repo.get_friendship_status(creator_id, other_user_id)
            if not friendship or friendship.status != FriendshipStatus.ACCEPTED:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only start conversations with friends"
                )
            
            # Check if private conversation already exists
            existing_conversation = await self.chat_repo.get_private_conversation(creator_id, other_user_id)
            if existing_conversation:
                return await self._build_conversation_response(existing_conversation, creator_id)
        
        # Validate all participants exist
        for participant_id in conversation_data.participant_ids:
            stmt = select(User).where(User.id == participant_id)
            result = await self.db.execute(stmt)
            user = result.scalar_one_or_none()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"User with ID {participant_id} not found"
                )
        
        # Create conversation
        conversation = await self.chat_repo.create_conversation(
            creator_id, 
            conversation_data.participant_ids, 
            conversation_data.type,
            conversation_data.name
        )
        
        return await self._build_conversation_response(conversation, creator_id)
    
    async def get_user_conversations(self, user_id: int, limit: int = 20, offset: int = 0) -> ConversationList:
        """Get user's conversations with latest messages and unread counts"""
        conversations, total_count = await self.chat_repo.get_user_conversations(user_id, limit, offset)
        
        conversation_responses = []
        for conversation in conversations:
            conversation_response = await self._build_conversation_response(conversation, user_id)
            conversation_responses.append(conversation_response)
        
        return ConversationList(
            conversations=conversation_responses,
            total_count=total_count
        )
    
    async def get_conversation(self, conversation_id: int, user_id: int) -> Conversation:
        """Get a specific conversation"""
        # Check if user is participant
        if not await self.chat_repo.is_user_in_conversation(user_id, conversation_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a participant in this conversation"
            )
        
        conversation = await self.chat_repo.get_conversation_by_id(conversation_id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        return await self._build_conversation_response(conversation, user_id)
    
    async def send_message(self, user_id: int, message_data: MessageCreate) -> Message:
        """Send a message in a conversation"""
        # Check if user is participant
        if not await self.chat_repo.is_user_in_conversation(user_id, message_data.conversation_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a participant in this conversation"
            )
        
        # Create message
        message = await self.chat_repo.create_message(
            message_data.conversation_id,
            user_id,
            message_data.content,
            message_data.message_type
        )
        
        # Convert to response format
        message_response = await self._build_message_response(message)
        
        # Ensure all conversation participants are in the room before broadcasting
        participant_ids = await self._ensure_participants_in_room(message_data.conversation_id)
        
        # Broadcast message via WebSocket (primary method)
        await connection_manager.broadcast_message(
            message_data.conversation_id,
            message_response.dict(),
            user_id
        )
        
        # Fallback: Send directly to any participants who might not be in the room
        message_data_dict = message_response.dict()
        outgoing_message = {
            "type": "message",
            "conversation_id": message_data.conversation_id,
            "message": message_data_dict,
            "timestamp": message_response.created_at.isoformat()
        }
        
        for participant_id in participant_ids:
            if participant_id != user_id and connection_manager.is_user_online(participant_id):
                await connection_manager.send_personal_message(participant_id, outgoing_message)
        
        return message_response
    
    async def get_conversation_messages(
        self, 
        conversation_id: int, 
        user_id: int, 
        limit: int = 50, 
        before_message_id: Optional[int] = None
    ) -> MessageList:
        """Get messages for a conversation"""
        # Check if user is participant
        if not await self.chat_repo.is_user_in_conversation(user_id, conversation_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a participant in this conversation"
            )
        
        messages, has_more = await self.chat_repo.get_conversation_messages(
            conversation_id, limit, before_message_id
        )
        
        message_responses = []
        for message in messages:
            message_response = await self._build_message_response(message)
            message_responses.append(message_response)
        
        return MessageList(
            messages=message_responses,
            total_count=len(message_responses),
            has_more=has_more
        )
    
    async def update_message(self, message_id: int, user_id: int, update_data: MessageUpdate) -> Message:
        """Update a message"""
        # Get message
        message = await self.chat_repo.get_message_by_id(message_id)
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found"
            )
        
        # Check if user is the sender
        if message.sender_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only edit your own messages"
            )
        
        # Update message
        updated_message = await self.chat_repo.update_message(message_id, update_data.content)
        if not updated_message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update message"
            )
        
        return await self._build_message_response(updated_message)
    
    async def delete_message(self, message_id: int, user_id: int) -> Dict[str, str]:
        """Delete a message"""
        # Get message
        message = await self.chat_repo.get_message_by_id(message_id)
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found"
            )
        
        # Check if user is the sender
        if message.sender_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own messages"
            )
        
        # Delete message
        success = await self.chat_repo.delete_message(message_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete message"
            )
        
        return {"message": "Message deleted successfully"}
    
    async def mark_conversation_as_read(self, conversation_id: int, user_id: int) -> Dict[str, str]:
        """Mark conversation as read for user"""
        # Check if user is participant
        if not await self.chat_repo.is_user_in_conversation(user_id, conversation_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a participant in this conversation"
            )
        
        # Update last read timestamp
        success = await self.chat_repo.update_last_read(user_id, conversation_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update read status"
            )
        
        return {"message": "Conversation marked as read"}
    
    async def join_conversation_room(self, user_id: int, conversation_id: int):
        """Join user to conversation room for WebSocket updates"""
        # Check if user is participant
        if not await self.chat_repo.is_user_in_conversation(user_id, conversation_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a participant in this conversation"
            )
        
        # Join room in connection manager
        connection_manager.join_room(user_id, conversation_id)
    
    async def leave_conversation_room(self, user_id: int, conversation_id: int):
        """Remove user from conversation room"""
        connection_manager.leave_room(user_id, conversation_id)
    
    async def handle_typing_indicator(self, user_id: int, conversation_id: int, is_typing: bool):
        """Handle typing indicator"""
        # Check if user is participant
        if not await self.chat_repo.is_user_in_conversation(user_id, conversation_id):
            return
        
        # Get user data
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user:
            user_data = {
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name
            }
            
            await connection_manager.broadcast_typing_indicator(
                conversation_id, user_id, is_typing, user_data
            )
    
    async def _ensure_participants_in_room(self, conversation_id: int):
        """Ensure all active participants of a conversation are joined to the WebSocket room"""
        # Get all active participants in the conversation
        conversation = await self.chat_repo.get_conversation_by_id(conversation_id)
        if not conversation:
            return
        
        # Join all active participants who are online to the room
        for participant in conversation.participants:
            if participant.is_active:
                user_id = participant.user_id
                # Only join if user is connected to WebSocket
                if connection_manager.is_user_online(user_id):
                    connection_manager.join_room(user_id, conversation_id)
        
        # Also broadcast directly to all online participants who might not be in the room yet
        # This ensures message delivery even if room management fails
        return [p.user_id for p in conversation.participants if p.is_active]
    
    async def _build_conversation_response(self, conversation, user_id: int) -> Conversation:
        """Build conversation response with additional data"""
        # Get participants
        participants = []
        for participant in conversation.participants:
            if participant.is_active:
                participants.append({
                    "id": participant.id,
                    "user_id": participant.user_id,
                    "joined_at": participant.joined_at,
                    "last_read_at": participant.last_read_at,
                    "is_active": participant.is_active,
                    "user": {
                        "id": participant.user.id,
                        "username": participant.user.username,
                        "full_name": participant.user.full_name
                    }
                })
        
        # Get latest message
        latest_message = await self.chat_repo.get_latest_message(conversation.id)
        latest_message_response = None
        if latest_message:
            latest_message_response = await self._build_message_response(latest_message)
        
        # Get unread count
        unread_count = await self.chat_repo.get_unread_count(user_id, conversation.id)
        
        return Conversation(
            id=conversation.id,
            type=conversation.type,
            name=conversation.name,
            created_by=conversation.created_by,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            last_message_at=conversation.last_message_at,
            participants=participants,
            last_message=latest_message_response,
            unread_count=unread_count
        )
    
    async def _build_message_response(self, message) -> Message:
        """Build message response"""
        return Message(
            id=message.id,
            conversation_id=message.conversation_id,
            sender_id=message.sender_id,
            content=message.content,
            message_type=message.message_type,
            is_edited=message.is_edited,
            is_deleted=message.is_deleted,
            created_at=message.created_at,
            updated_at=message.updated_at,
            sender={
                "id": message.sender.id,
                "username": message.sender.username,
                "full_name": message.sender.full_name
            }
        ) 