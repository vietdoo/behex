from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, update, delete
from sqlalchemy.orm import selectinload, joinedload
from typing import List, Optional, Tuple
from datetime import datetime

from app.models.chat import Conversation, ConversationParticipant, Message
from app.models.user import User
from app.schemas.chat import ConversationType, MessageType


class ChatRepository:
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # Conversation Management
    async def create_conversation(
        self, 
        creator_id: int, 
        participant_ids: List[int], 
        conversation_type: ConversationType = ConversationType.PRIVATE,
        name: Optional[str] = None
    ) -> Conversation:
        """Create a new conversation"""
        conversation = Conversation(
            type=conversation_type,
            name=name,
            created_by=creator_id
        )
        self.db.add(conversation)
        await self.db.flush()  # Get the ID without committing
        
        # Add all participants (including creator)
        all_participants = list(set([creator_id] + participant_ids))
        for user_id in all_participants:
            participant = ConversationParticipant(
                conversation_id=conversation.id,
                user_id=user_id
            )
            self.db.add(participant)
        
        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation
    
    async def get_conversation_by_id(self, conversation_id: int) -> Optional[Conversation]:
        """Get conversation by ID with participants and latest message"""
        stmt = select(Conversation).options(
            selectinload(Conversation.participants).selectinload(ConversationParticipant.user)
        ).where(Conversation.id == conversation_id)
        
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_private_conversation(self, user1_id: int, user2_id: int) -> Optional[Conversation]:
        """Get existing private conversation between two users"""
        stmt = select(Conversation).join(ConversationParticipant).where(
            and_(
                Conversation.type == ConversationType.PRIVATE,
                ConversationParticipant.user_id.in_([user1_id, user2_id])
            )
        ).group_by(Conversation.id).having(
            func.count(ConversationParticipant.user_id) == 2
        )
        
        result = await self.db.execute(stmt)
        conversation = result.scalar_one_or_none()
        
        if conversation:
            # Verify both users are participants
            participants_stmt = select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == conversation.id
            )
            participants_result = await self.db.execute(participants_stmt)
            participants = participants_result.scalars().all()
            
            participant_ids = [p.user_id for p in participants]
            if user1_id in participant_ids and user2_id in participant_ids:
                return conversation
        
        return None
    
    async def get_user_conversations(
        self, 
        user_id: int, 
        limit: int = 20, 
        offset: int = 0
    ) -> Tuple[List[Conversation], int]:
        """Get user's conversations with latest message and unread count"""
        # Get conversations where user is a participant
        conversations_stmt = select(Conversation).join(ConversationParticipant).options(
            selectinload(Conversation.participants).selectinload(ConversationParticipant.user)
        ).where(
            and_(
                ConversationParticipant.user_id == user_id,
                ConversationParticipant.is_active == True
            )
        ).order_by(desc(Conversation.last_message_at)).offset(offset).limit(limit)
        
        conversations_result = await self.db.execute(conversations_stmt)
        conversations = conversations_result.scalars().all()
        
        # Get total count
        count_stmt = select(func.count(Conversation.id)).join(ConversationParticipant).where(
            and_(
                ConversationParticipant.user_id == user_id,
                ConversationParticipant.is_active == True
            )
        )
        count_result = await self.db.execute(count_stmt)
        total_count = count_result.scalar()
        
        return conversations, total_count
    
    async def is_user_in_conversation(self, user_id: int, conversation_id: int) -> bool:
        """Check if user is a participant in the conversation"""
        stmt = select(ConversationParticipant).where(
            and_(
                ConversationParticipant.user_id == user_id,
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.is_active == True
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None
    
    # Message Management
    async def create_message(
        self, 
        conversation_id: int, 
        sender_id: int, 
        content: str, 
        message_type: MessageType = MessageType.TEXT
    ) -> Message:
        """Create a new message"""
        message = Message(
            conversation_id=conversation_id,
            sender_id=sender_id,
            content=content,
            message_type=message_type
        )
        self.db.add(message)
        
        # Update conversation's last_message_at
        await self.db.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(last_message_at=func.now())
        )
        
        await self.db.commit()
        await self.db.refresh(message)
        
        # Load sender relationship
        await self.db.refresh(message, ['sender'])
        
        return message
    
    async def get_message_by_id(self, message_id: int) -> Optional[Message]:
        """Get message by ID with sender info"""
        stmt = select(Message).options(
            selectinload(Message.sender)
        ).where(Message.id == message_id)
        
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_conversation_messages(
        self, 
        conversation_id: int, 
        limit: int = 50, 
        before_message_id: Optional[int] = None
    ) -> Tuple[List[Message], bool]:
        """Get messages for a conversation with pagination"""
        stmt = select(Message).options(
            selectinload(Message.sender)
        ).where(
            and_(
                Message.conversation_id == conversation_id,
                Message.is_deleted == False
            )
        )
        
        if before_message_id:
            stmt = stmt.where(Message.id < before_message_id)
        
        stmt = stmt.order_by(desc(Message.created_at)).limit(limit + 1)
        
        result = await self.db.execute(stmt)
        messages = result.scalars().all()
        
        has_more = len(messages) > limit
        if has_more:
            messages = messages[:limit]
        
        # Return messages in chronological order (oldest first)
        messages.reverse()
        
        return messages, has_more
    
    async def update_message(self, message_id: int, content: str) -> Optional[Message]:
        """Update message content"""
        stmt = update(Message).where(
            Message.id == message_id
        ).values(
            content=content,
            is_edited=True,
            updated_at=func.now()
        ).returning(Message)
        
        result = await self.db.execute(stmt)
        await self.db.commit()
        
        updated_message = result.scalar_one_or_none()
        if updated_message:
            await self.db.refresh(updated_message, ['sender'])
        
        return updated_message
    
    async def delete_message(self, message_id: int) -> bool:
        """Soft delete a message"""
        stmt = update(Message).where(
            Message.id == message_id
        ).values(
            is_deleted=True,
            content="[This message was deleted]",
            updated_at=func.now()
        )
        
        result = await self.db.execute(stmt)
        await self.db.commit()
        
        return result.rowcount > 0
    
    # Read Receipts & Status
    async def update_last_read(self, user_id: int, conversation_id: int) -> bool:
        """Update user's last read timestamp for a conversation"""
        stmt = update(ConversationParticipant).where(
            and_(
                ConversationParticipant.user_id == user_id,
                ConversationParticipant.conversation_id == conversation_id
            )
        ).values(last_read_at=func.now())
        
        result = await self.db.execute(stmt)
        await self.db.commit()
        
        return result.rowcount > 0
    
    async def get_unread_count(self, user_id: int, conversation_id: int) -> int:
        """Get unread message count for user in conversation"""
        # Get user's last read timestamp
        participant_stmt = select(ConversationParticipant).where(
            and_(
                ConversationParticipant.user_id == user_id,
                ConversationParticipant.conversation_id == conversation_id
            )
        )
        participant_result = await self.db.execute(participant_stmt)
        participant = participant_result.scalar_one_or_none()
        
        if not participant:
            return 0
        
        # Count messages after last read timestamp
        if participant.last_read_at:
            unread_stmt = select(func.count(Message.id)).where(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.created_at > participant.last_read_at,
                    Message.sender_id != user_id,  # Exclude own messages
                    Message.is_deleted == False
                )
            )
        else:
            # If never read, count all messages except own
            unread_stmt = select(func.count(Message.id)).where(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.sender_id != user_id,
                    Message.is_deleted == False
                )
            )
        
        unread_result = await self.db.execute(unread_stmt)
        return unread_result.scalar() or 0
    
    async def get_latest_message(self, conversation_id: int) -> Optional[Message]:
        """Get the latest message in a conversation"""
        stmt = select(Message).options(
            selectinload(Message.sender)
        ).where(
            and_(
                Message.conversation_id == conversation_id,
                Message.is_deleted == False
            )
        ).order_by(desc(Message.created_at)).limit(1)
        
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    # Participant Management
    async def add_participant(self, conversation_id: int, user_id: int) -> ConversationParticipant:
        """Add a participant to a conversation"""
        participant = ConversationParticipant(
            conversation_id=conversation_id,
            user_id=user_id
        )
        self.db.add(participant)
        await self.db.commit()
        await self.db.refresh(participant)
        return participant
    
    async def remove_participant(self, conversation_id: int, user_id: int) -> bool:
        """Remove a participant from a conversation"""
        stmt = update(ConversationParticipant).where(
            and_(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id == user_id
            )
        ).values(is_active=False)
        
        result = await self.db.execute(stmt)
        await self.db.commit()
        
        return result.rowcount > 0 