#!/usr/bin/env python3
"""
Test script for token-level streaming WebSocket.

Usage:
    python test_streaming.py [--token YOUR_JWT_TOKEN]
    
For development testing, start the agent with:
    ALLOW_TEST_TOKEN=true python claude_agent_api_v1.py
    
Then run without --token to use the test token.
"""

import asyncio
import json
import sys
import websockets

# Default to "test" token for development (requires ALLOW_TEST_TOKEN=true on server)
TEST_TOKEN = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--token" else "test"

WS_URL = f"ws://localhost:8002/ws/stream?token={TEST_TOKEN}"


async def test_streaming():
    print(f"🔌 Connecting to {WS_URL[:50]}...")
    
    try:
        async with websockets.connect(WS_URL) as ws:
            print("✅ Connected!")
            
            # Wait for session creation
            response = await ws.recv()
            data = json.loads(response)
            print(f"📨 {data}")
            
            # Send a test prompt
            prompt = "Hello! Can you count from 1 to 5 slowly?"
            print(f"\n📤 Sending: {prompt}")
            
            await ws.send(json.dumps({
                "type": "chat",
                "prompt": prompt
            }))
            
            # Receive streaming response
            print("\n📥 Streaming response:")
            print("-" * 40)
            
            full_response = ""
            while True:
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=30)
                    data = json.loads(response)
                    
                    if data["type"] == "delta":
                        # Print each token as it arrives (no newline)
                        token = data["content"]
                        print(token, end="", flush=True)
                        full_response += token
                    
                    elif data["type"] == "tool_use":
                        print(f"\n🔧 Tool: {data['name']}")
                    
                    elif data["type"] == "tool_result":
                        print(f"\n📋 Result: {data['content'][:100]}...")
                    
                    elif data["type"] == "complete":
                        print("\n" + "-" * 40)
                        print("✅ Stream complete!")
                        break
                    
                    elif data["type"] == "error":
                        print(f"\n❌ Error: {data['error']}")
                        break
                        
                except asyncio.TimeoutError:
                    print("\n⏰ Timeout waiting for response")
                    break
            
            print(f"\n📊 Total tokens received: ~{len(full_response.split())} words")
            
    except websockets.exceptions.InvalidStatusCode as e:
        if e.status_code == 4001:
            print("❌ Authentication failed. Please provide a valid JWT token:")
            print("   python test_streaming.py --token YOUR_JWT_TOKEN")
        else:
            print(f"❌ Connection failed: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    print("🧪 Token Streaming Test")
    print("=" * 40)
    asyncio.run(test_streaming())
