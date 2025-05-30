#!/usr/bin/env python3
"""
Test script to verify WebSocket message broadcasting
"""
import asyncio
import websockets
import json
import sys

async def test_websocket_connection(token, user_name):
    """Test WebSocket connection and message handling"""
    uri = f"ws://localhost:10000/api/v1/ws/chat?token={token}"
    
    try:
        async with websockets.connect(uri) as websocket:
            print(f"[{user_name}] Connected to WebSocket")
            
            # Listen for messages
            async for message in websocket:
                data = json.loads(message)
                print(f"[{user_name}] Received: {data}")
                
    except Exception as e:
        print(f"[{user_name}] WebSocket error: {e}")

async def send_test_message(token, conversation_id, message_content):
    """Send a test message via WebSocket"""
    uri = f"ws://localhost:10000/api/v1/ws/chat?token={token}"
    
    try:
        async with websockets.connect(uri) as websocket:
            print(f"Connected to send message")
            
            # Send message
            message_data = {
                "type": "message",
                "conversation_id": conversation_id,
                "content": message_content,
                "message_type": "text"
            }
            
            await websocket.send(json.dumps(message_data))
            print(f"Sent message: {message_content}")
            
            # Wait for response
            response = await websocket.recv()
            print(f"Response: {response}")
            
    except Exception as e:
        print(f"Error sending message: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_websocket.py <command> [args...]")
        print("Commands:")
        print("  listen <token> <user_name>")
        print("  send <token> <conversation_id> <message>")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "listen" and len(sys.argv) == 4:
        token = sys.argv[2]
        user_name = sys.argv[3]
        asyncio.run(test_websocket_connection(token, user_name))
        
    elif command == "send" and len(sys.argv) == 5:
        token = sys.argv[2]
        conversation_id = int(sys.argv[3])
        message = sys.argv[4]
        asyncio.run(send_test_message(token, conversation_id, message))
        
    else:
        print("Invalid command or arguments")
        sys.exit(1) 