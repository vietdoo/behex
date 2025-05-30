# Chat WebSocket Troubleshooting Guide

## Problem: Messages Not Broadcasting to Other Users

### Issue Description
When a user sends a message in a chat conversation, other participants don't see the message in real-time. They only see it when they refresh the page (F5).

### Root Cause
The issue was that users weren't automatically joined to WebSocket conversation rooms, which are required for message broadcasting to work.

## Fixes Applied

### 1. Automatic Room Joining on WebSocket Connection
- **File**: `app/api/v1/endpoints/websocket.py`
- **Fix**: Added `auto_join_user_rooms()` function that automatically joins users to all their conversation rooms when they connect to WebSocket
- **Code**: Users are now auto-joined to rooms on WebSocket connection

### 2. Participant Room Management
- **File**: `app/services/chat.py`
- **Fix**: Added `_ensure_participants_in_room()` method to ensure all conversation participants are in the room before broadcasting
- **Code**: Called before every message broadcast

### 3. Fallback Broadcasting
- **File**: `app/services/chat.py`
- **Fix**: Added fallback mechanism that sends messages directly to online participants even if room broadcasting fails
- **Code**: Dual broadcasting approach for reliability

### 4. Enhanced Logging
- **File**: `app/core/websocket.py`
- **Fix**: Added detailed logging to track broadcasting success/failure
- **Code**: Logs participant counts, connection status, and broadcast results

## Testing the Fix

### Method 1: Using the HTML Test Client
1. Open `chat_example.html` in two different browser tabs/windows
2. Use different JWT tokens for each user
3. Connect both users to the same conversation
4. Send a message from one user
5. Verify the other user receives it without refreshing

### Method 2: Using the Python Test Script
```bash
# Terminal 1 - Listen for messages (User 1)
python test_websocket.py listen "JWT_TOKEN_USER1" "User1"

# Terminal 2 - Listen for messages (User 2)
python test_websocket.py listen "JWT_TOKEN_USER2" "User2"

# Terminal 3 - Send a message
python test_websocket.py send "JWT_TOKEN_USER1" 1 "Hello from User1!"
```

### Method 3: Frontend Integration
Your Next.js frontend should now receive real-time messages if:
1. Both users are connected to WebSocket (`/api/v1/ws/chat`)
2. Both users have valid JWT tokens
3. Both users are participants in the same conversation

## Key Changes Summary

1. **WebSocket URL**: Fixed to `/api/v1/ws/chat` (was `/ws/chat`)
2. **Auto Room Joining**: Users automatically join all their conversation rooms on connect
3. **Message Broadcasting**: Enhanced with fallback mechanisms
4. **Debugging**: Added comprehensive logging for troubleshooting

## Debugging WebSocket Issues

### Check Application Logs
```bash
docker-compose logs app --tail=100 --follow
```

Look for:
- `User X auto-joined to Y conversation rooms`
- `Broadcasting to room X: Y participants`
- `Successfully sent message to X/Y participants`

### Common Issues

1. **403 Forbidden on WebSocket**: Check JWT token validity
2. **No participants in room**: Users may not be auto-joined correctly
3. **Message not broadcasting**: Check if recipients are online and connected

### WebSocket Connection Status
- **Connected**: User appears in `connection_manager.online_users`
- **In Room**: User appears in `connection_manager.room_participants[conversation_id]`
- **Message Flow**: Sender → Room Broadcast → Individual Connections

## Frontend Requirements

Ensure your Next.js frontend:
1. Connects to correct WebSocket URL: `ws://localhost:10000/api/v1/ws/chat?token=JWT_TOKEN`
2. Handles incoming message events properly
3. Maintains connection while user is active in chat
4. Reconnects on connection loss

## Performance Notes

- Room management is now automatic and efficient
- Fallback broadcasting ensures message delivery
- Connection cleanup happens on disconnect
- Maximum room participants: No limit (scales with participants) 