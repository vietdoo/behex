import json
import asyncio
import logging
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.core.websocket import connection_manager
from app.schemas.chat import IncomingMessage, WebSocketMessageType, MessageType
from app.services.chat import ChatService
from app.repositories.user import UserRepository
from app.models.user import User

logger = logging.getLogger(__name__)


async def get_user_from_token(token: str, db: AsyncSession) -> Optional[User]:
    """Get user from WebSocket token"""
    try:
        payload = decode_token(token)
        if not payload or payload.get("type") != "access":
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        user_repo = UserRepository(db)
        user = await user_repo.get_by_id(int(user_id))
        
        if not user or not user.is_active:
            return None
        
        return user
    except Exception as e:
        logger.error(f"Error getting user from token: {e}")
        return None


async def auto_join_user_rooms(user_id: int, db: AsyncSession):
    """Automatically join user to all their conversation rooms"""
    try:
        from app.repositories.chat import ChatRepository
        chat_repo = ChatRepository(db)
        
        # Get all user's conversations
        conversations, _ = await chat_repo.get_user_conversations(user_id, limit=1000, offset=0)
        
        # Join user to all conversation rooms
        for conversation in conversations:
            connection_manager.join_room(user_id, conversation.id)
        
        print(f"[BEHEX DEBUG] User {user_id} auto-joined to {len(conversations)} \
            conversation rooms: {[conversation.id for conversation in conversations]}")
        logger.info(f"User {user_id} auto-joined to {len(conversations)} conversation rooms")
    except Exception as e:
        print(f"[BEHEX DEBUG] Error auto-joining user {user_id} to rooms: {e}")
        logger.error(f"Error auto-joining user {user_id} to rooms: {e}")


async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
    db: AsyncSession = Depends(get_db)
):
    """WebSocket endpoint for real-time chat"""
    print(f"[BEHEX DEBUG] Websocket endpoint called with token: {token}")
    user = await get_user_from_token(token, db)
    print(f"[BEHEX DEBUG] Websocket user: {user.username if user else 'None'}")
    
    if not user:
        print(f"[BEHEX DEBUG] Websocket user not found")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    # Connect user to WebSocket
    await connection_manager.connect(websocket, user.id)
    
    # Automatically join user to all their conversation rooms
    await auto_join_user_rooms(user.id, db)
    
    try:
        # Initialize chat service
        chat_service = ChatService(db)
        
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # Parse incoming message
                try:
                    incoming_message = IncomingMessage(**message_data)
                except Exception as e:
                    await connection_manager.send_error(
                        user.id, 
                        f"Invalid message format: {str(e)}", 
                        "INVALID_FORMAT"
                    )
                    continue
                
                # Handle different message types
                await handle_websocket_message(
                    incoming_message, user.id, chat_service, db
                )
                
            except json.JSONDecodeError:
                await connection_manager.send_error(
                    user.id, 
                    "Invalid JSON format", 
                    "INVALID_JSON"
                )
                continue
            
            except WebSocketDisconnect:
                break
            
            except Exception as e:
                logger.error(f"Error handling WebSocket message for user {user.id}: {e}")
                await connection_manager.send_error(
                    user.id, 
                    "Internal server error", 
                    "INTERNAL_ERROR"
                )
                continue
    
    except WebSocketDisconnect:
        print(f"[BEHEX DEBUG] Websocket disconnected")
        pass
    except Exception as e:
        print(f"[BEHEX DEBUG] Websocket error: {e}")
        logger.error(f"WebSocket error for user {user.id}: {e}")
    finally:
        # Disconnect user
        print(f"[BEHEX DEBUG] Websocket finally")
        connection_manager.disconnect(user.id)


async def handle_websocket_message(
    message: IncomingMessage, 
    user_id: int, 
    chat_service: ChatService,
    db: AsyncSession
):
    """Handle different types of WebSocket messages"""
    
    try:
        if message.type == WebSocketMessageType.MESSAGE:
            # Send message
            if not message.conversation_id or not message.content:
                await connection_manager.send_error(
                    user_id, 
                    "conversation_id and content are required for messages", 
                    "MISSING_FIELDS"
                )
                return
            
            # Create message through service (which will broadcast it)
            from app.schemas.chat import MessageCreate
            message_data = MessageCreate(
                conversation_id=message.conversation_id,
                content=message.content,
                message_type=message.message_type or MessageType.TEXT
            )
            
            try:
                await chat_service.send_message(user_id, message_data)
            except HTTPException as e:
                await connection_manager.send_error(
                    user_id, 
                    e.detail, 
                    "SEND_MESSAGE_ERROR"
                )
        
        elif message.type == WebSocketMessageType.TYPING:
            # Handle typing indicator
            if not message.conversation_id:
                await connection_manager.send_error(
                    user_id, 
                    "conversation_id is required for typing indicators", 
                    "MISSING_FIELDS"
                )
                return
            
            # Determine if user is typing (default to True if not specified)
            is_typing = message.content != "false" if message.content else True
            
            await chat_service.handle_typing_indicator(
                user_id, message.conversation_id, is_typing
            )
        
        elif message.type == WebSocketMessageType.READ_RECEIPT:
            # Mark conversation as read
            if not message.conversation_id:
                await connection_manager.send_error(
                    user_id, 
                    "conversation_id is required for read receipts", 
                    "MISSING_FIELDS"
                )
                return
            
            try:
                await chat_service.mark_conversation_as_read(message.conversation_id, user_id)
                
                # Broadcast read receipt to other participants
                from sqlalchemy import select
                from app.models.user import User
                stmt = select(User).where(User.id == user_id)
                result = await db.execute(stmt)
                user = result.scalar_one_or_none()
                
                if user:
                    user_data = {
                        "id": user.id,
                        "username": user.username,
                        "full_name": user.full_name
                    }
                    
                    # For read receipts, we use the last message ID in the conversation
                    # This could be enhanced to track specific message read receipts
                    await connection_manager.broadcast_read_receipt(
                        message.conversation_id, user_id, 0, user_data
                    )
                    
            except HTTPException as e:
                await connection_manager.send_error(
                    user_id, 
                    e.detail, 
                    "READ_RECEIPT_ERROR"
                )
        
        elif message.type == WebSocketMessageType.PING:
            # Respond to ping with pong
            await connection_manager.send_pong(user_id)
        
        else:
            await connection_manager.send_error(
                user_id, 
                f"Unsupported message type: {message.type}", 
                "UNSUPPORTED_TYPE"
            )
    
    except Exception as e:
        logger.error(f"Error handling message type {message.type} for user {user_id}: {e}")
        await connection_manager.send_error(
            user_id, 
            "Error processing message", 
            "PROCESSING_ERROR"
        ) 