#!/usr/bin/env python3
"""
WebSocket Test Client for Agent Endpoints.

Tests the WebSocket streaming endpoints:
- /ws/stream (pure streaming)
- /hybrid/ws/stream (hybrid agent)
- /ws/chat (legacy SDK)

Usage:
    # Test against local server
    python scripts/test_websocket.py
    
    # Test specific endpoint
    python scripts/test_websocket.py --endpoint hybrid
    
    # Test with custom prompt
    python scripts/test_websocket.py --prompt "Show me incidents"
    
    # Test against custom host
    python scripts/test_websocket.py --host ws://localhost:8002
"""

import argparse
import asyncio
import json
import sys

try:
    import websockets
except ImportError:
    print("Installing websockets...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets"])
    import websockets


async def test_websocket(
    host: str,
    endpoint: str,
    prompt: str,
    token: str = "dev-token",
    org_id: str = "test-org",
):
    """Test a WebSocket endpoint."""
    
    # Build WebSocket URL
    ws_url = f"{host}/{endpoint}?token={token}&org_id={org_id}"
    
    print("=" * 60)
    print(f"WebSocket Test: {endpoint}")
    print("=" * 60)
    print(f"URL: {ws_url}")
    print(f"Prompt: {prompt}")
    print("-" * 60)
    
    try:
        async with websockets.connect(ws_url) as ws:
            # Wait for session_created
            print("Waiting for session...")
            response = await asyncio.wait_for(ws.recv(), timeout=10)
            session_data = json.loads(response)
            
            if session_data.get("type") == "session_created":
                print(f"✓ Session created: {session_data.get('session_id', 'N/A')}")
                print(f"  Agent type: {session_data.get('agent_type', 'N/A')}")
                print(f"  Tools: {session_data.get('total_tools', 'N/A')}")
            else:
                print(f"? Unexpected first message: {session_data}")
            
            print("-" * 60)
            
            # Send chat message
            message = {
                "type": "chat",
                "prompt": prompt,
                "org_id": org_id,
            }
            await ws.send(json.dumps(message))
            print(f"→ Sent: {prompt[:50]}...")
            print("-" * 60)
            print("Streaming Response:")
            print()
            
            # Receive streaming response
            full_response = ""
            
            while True:
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=60)
                    event = json.loads(response)
                    
                    event_type = event.get("type")
                    
                    if event_type == "delta":
                        content = event.get("content", "")
                        print(content, end="", flush=True)
                        full_response += content
                        
                    elif event_type == "text":
                        # Legacy block-level output
                        content = event.get("content", "")
                        print(content, end="", flush=True)
                        full_response += content
                        
                    elif event_type == "tool_use":
                        tool_name = event.get("name", "unknown")
                        print(f"\n[🔧 Tool: {tool_name}]", flush=True)
                        
                    elif event_type == "tool_result":
                        content = event.get("content", "")[:100]
                        is_error = event.get("is_error", False)
                        status = "❌" if is_error else "✓"
                        print(f"[{status} Result: {content}...]", flush=True)
                        
                    elif event_type == "thinking":
                        content = event.get("content", "")[:50]
                        print(f"\n[💭 Thinking: {content}...]", flush=True)
                        
                    elif event_type == "complete":
                        print("\n")
                        print("-" * 60)
                        print("✓ Response complete")
                        break
                        
                    elif event_type == "error":
                        error = event.get("error", "Unknown error")
                        print(f"\n❌ Error: {error}")
                        break
                        
                    elif event_type == "interrupted":
                        print("\n⚠️ Interrupted")
                        break
                        
                    elif event_type == "ping":
                        # Respond to ping
                        await ws.send(json.dumps({"type": "pong"}))
                        
                    else:
                        print(f"\n[? Unknown event: {event_type}]", flush=True)
                        
                except asyncio.TimeoutError:
                    print("\n⏰ Timeout waiting for response")
                    break
            
            print(f"Response length: {len(full_response)} chars")
            print("=" * 60)
            
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"❌ Connection failed: {e}")
        if e.status_code == 4001:
            print("   Authentication failed - check your token")
    except ConnectionRefusedError:
        print(f"❌ Connection refused - is the server running at {host}?")
    except Exception as e:
        print(f"❌ Error: {e}")


async def test_all_endpoints(host: str, prompt: str):
    """Test all WebSocket endpoints."""
    endpoints = [
        ("ws/stream", "Pure Streaming"),
        ("hybrid/ws/stream", "Hybrid Agent"),
    ]
    
    for endpoint, name in endpoints:
        print(f"\n\n{'#' * 60}")
        print(f"# Testing: {name}")
        print(f"{'#' * 60}\n")
        
        await test_websocket(host, endpoint, prompt)
        
        # Brief pause between tests
        await asyncio.sleep(1)


def main():
    parser = argparse.ArgumentParser(description="Test WebSocket endpoints")
    parser.add_argument(
        "--host",
        default="ws://localhost:8002",
        help="WebSocket host URL (default: ws://localhost:8002)"
    )
    parser.add_argument(
        "--endpoint",
        choices=["streaming", "hybrid", "legacy", "all"],
        default="all",
        help="Endpoint to test (default: all)"
    )
    parser.add_argument(
        "--prompt",
        default="Hello! What can you help me with?",
        help="Prompt to send"
    )
    parser.add_argument(
        "--token",
        default="dev-test-token",
        help="Auth token (default: dev-test-token)"
    )
    
    args = parser.parse_args()
    
    endpoint_map = {
        "streaming": "ws/stream",
        "hybrid": "hybrid/ws/stream",
        "legacy": "ws/chat",
    }
    
    if args.endpoint == "all":
        asyncio.run(test_all_endpoints(args.host, args.prompt))
    else:
        endpoint = endpoint_map.get(args.endpoint, args.endpoint)
        asyncio.run(test_websocket(args.host, endpoint, args.prompt, args.token))


if __name__ == "__main__":
    main()
