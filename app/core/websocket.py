import json
import asyncio
from typing import Dict, List, Set, Optional
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime
import logging

from app.schemas.chat import WebSocketMessageType, OutgoingMessage, ChatUser

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for chat functionality"""
    
    def __init__(self):
        # Active connections: user_id -> WebSocket
        self.active_connections: Dict[int, WebSocket] = {}
        
        # User rooms: user_id -> Set[conversation_id]
        self.user_rooms: Dict[int, Set[int]] = {}
        
        # Room participants: conversation_id -> Set[user_id]
        self.room_participants: Dict[int, Set[int]] = {}
        
        # Typing indicators: conversation_id -> Set[user_id]
        self.typing_users: Dict[int, Set[int]] = {}
        
        # Online status tracking
        self.online_users: Set[int] = set()
        
        # User last seen timestamps
        self.last_seen: Dict[int, datetime] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int):
        """Accept new WebSocket connection"""
        await websocket.accept()
        
        # Disconnect existing connection if any
        if user_id in self.active_connections:
            try:
                old_websocket = self.active_connections[user_id]
                await old_websocket.close()
            except:
                pass
        
        self.active_connections[user_id] = websocket
        self.online_users.add(user_id)
        
        # Initialize user rooms if not exists
        if user_id not in self.user_rooms:
            self.user_rooms[user_id] = set()
        
        logger.info(f"User {user_id} connected to WebSocket")
        
        # Notify other users that this user is online
        await self.broadcast_user_status(user_id, is_online=True)
    
    def disconnect(self, user_id: int):
        """Handle WebSocket disconnection"""
        # Remove from active connections
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        
        # Remove from online users
        self.online_users.discard(user_id)
        
        # Update last seen
        self.last_seen[user_id] = datetime.utcnow()
        
        # Remove from all rooms
        if user_id in self.user_rooms:
            for conversation_id in self.user_rooms[user_id].copy():
                self.leave_room(user_id, conversation_id)
            del self.user_rooms[user_id]
        
        # Remove typing indicators
        for conversation_id in list(self.typing_users.keys()):
            self.typing_users[conversation_id].discard(user_id)
            if not self.typing_users[conversation_id]:
                del self.typing_users[conversation_id]
        
        logger.info(f"User {user_id} disconnected from WebSocket")
    
    def join_room(self, user_id: int, conversation_id: int):
        """Add user to a conversation room"""
        if user_id not in self.user_rooms:
            self.user_rooms[user_id] = set()
        
        self.user_rooms[user_id].add(conversation_id)
        
        if conversation_id not in self.room_participants:
            self.room_participants[conversation_id] = set()
        
        self.room_participants[conversation_id].add(user_id)
        
        logger.debug(f"User {user_id} joined room {conversation_id}")
    
    def leave_room(self, user_id: int, conversation_id: int):
        """Remove user from a conversation room"""
        if user_id in self.user_rooms:
            self.user_rooms[user_id].discard(conversation_id)
        
        if conversation_id in self.room_participants:
            self.room_participants[conversation_id].discard(user_id)
            if not self.room_participants[conversation_id]:
                del self.room_participants[conversation_id]
        
        logger.debug(f"User {user_id} left room {conversation_id}")
    
    async def send_personal_message(self, user_id: int, message: dict):
        """Send message to a specific user"""
        if user_id in self.active_connections:
            websocket = self.active_connections[user_id]
            try:
                await websocket.send_text(json.dumps(message, default=str))
                return True
            except Exception as e:
                logger.error(f"Error sending message to user {user_id}: {e}")
                # Remove failed connection
                self.disconnect(user_id)
                return False
        return False
    
    async def broadcast_to_room(self, conversation_id: int, message: dict, exclude_user: Optional[int] = None):
        """Broadcast message to all users in a conversation room"""
        if conversation_id not in self.room_participants:
            logger.warning(f"No participants found in room {conversation_id}")
            return
        
        participants = self.room_participants[conversation_id].copy()
        logger.info(f"Broadcasting to room {conversation_id}: {len(participants)} participants")
        
        if exclude_user:
            participants.discard(exclude_user)
            logger.info(f"Excluding user {exclude_user}, now broadcasting to {len(participants)} participants")
        
        # Send to all participants
        tasks = []
        successful_sends = 0
        for user_id in participants:
            if user_id in self.active_connections:
                task = self.send_personal_message(user_id, message)
                tasks.append(task)
            else:
                logger.warning(f"User {user_id} not in active connections")
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            successful_sends = sum(1 for result in results if result is True)
            logger.info(f"Successfully sent message to {successful_sends}/{len(tasks)} participants")
        else:
            logger.warning(f"No active connections found for room {conversation_id}")
    
    async def broadcast_message(self, conversation_id: int, message_data: dict, sender_id: int):
        """Broadcast new message to conversation participants"""
        outgoing_message = {
            "type": WebSocketMessageType.MESSAGE,
            "conversation_id": conversation_id,
            "message": message_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.broadcast_to_room(conversation_id, outgoing_message, exclude_user=sender_id)
    
    async def broadcast_typing_indicator(self, conversation_id: int, user_id: int, is_typing: bool, user_data: dict):
        """Broadcast typing indicator to conversation participants"""
        if conversation_id not in self.typing_users:
            self.typing_users[conversation_id] = set()
        
        if is_typing:
            self.typing_users[conversation_id].add(user_id)
        else:
            self.typing_users[conversation_id].discard(user_id)
        
        typing_message = {
            "type": WebSocketMessageType.TYPING,
            "conversation_id": conversation_id,
            "data": {
                "user": user_data,
                "is_typing": is_typing
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.broadcast_to_room(conversation_id, typing_message, exclude_user=user_id)
    
    async def broadcast_read_receipt(self, conversation_id: int, user_id: int, message_id: int, user_data: dict):
        """Broadcast read receipt to conversation participants"""
        read_receipt_message = {
            "type": WebSocketMessageType.READ_RECEIPT,
            "conversation_id": conversation_id,
            "data": {
                "user": user_data,
                "message_id": message_id,
                "read_at": datetime.utcnow().isoformat()
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.broadcast_to_room(conversation_id, read_receipt_message, exclude_user=user_id)
    
    async def broadcast_user_status(self, user_id: int, is_online: bool):
        """Broadcast user online/offline status to relevant conversations"""
        if user_id not in self.user_rooms:
            return
        
        status_message = {
            "type": WebSocketMessageType.USER_ONLINE if is_online else WebSocketMessageType.USER_OFFLINE,
            "data": {
                "user_id": user_id,
                "is_online": is_online,
                "timestamp": datetime.utcnow().isoformat()
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Send to all conversations this user is part of
        notified_users = set()
        for conversation_id in self.user_rooms[user_id]:
            if conversation_id in self.room_participants:
                for participant_id in self.room_participants[conversation_id]:
                    if participant_id != user_id and participant_id not in notified_users:
                        await self.send_personal_message(participant_id, status_message)
                        notified_users.add(participant_id)
    
    def get_online_users_in_conversation(self, conversation_id: int) -> List[int]:
        """Get list of online users in a conversation"""
        if conversation_id not in self.room_participants:
            return []
        
        online_users = []
        for user_id in self.room_participants[conversation_id]:
            if user_id in self.online_users:
                online_users.append(user_id)
        
        return online_users
    
    def is_user_online(self, user_id: int) -> bool:
        """Check if user is currently online"""
        return user_id in self.online_users
    
    def get_user_last_seen(self, user_id: int) -> Optional[datetime]:
        """Get user's last seen timestamp"""
        return self.last_seen.get(user_id)
    
    async def send_error(self, user_id: int, error_message: str, error_code: Optional[str] = None):
        """Send error message to user"""
        error_msg = {
            "type": WebSocketMessageType.ERROR,
            "data": {
                "message": error_message,
                "code": error_code
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.send_personal_message(user_id, error_msg)
    
    async def send_pong(self, user_id: int):
        """Send pong response to ping"""
        pong_msg = {
            "type": WebSocketMessageType.PONG,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.send_personal_message(user_id, pong_msg)


# Global connection manager instance
connection_manager = ConnectionManager() 