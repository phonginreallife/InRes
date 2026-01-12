"""
Streaming WebSocket Routes for Token-level LLM Streaming.

This module provides WebSocket endpoints that stream tokens directly
from the Anthropic API to the frontend in real-time.
"""

import asyncio
import json
import logging
import os
import uuid
from typing import Any, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from supabase_storage import extract_user_id_from_token

from streaming_agent import StreamingAgent, create_streaming_agent, INCIDENT_TOOLS

logger = logging.getLogger(__name__)

router = APIRouter()

# Store active streaming sessions
active_sessions: Dict[str, StreamingAgent] = {}


async def verify_token(token: str) -> tuple[bool, str]:
    """Verify JWT token and return (is_valid, user_id_or_error)."""
    if not token:
        return False, "Missing authentication token"
    
    try:
        user_id = extract_user_id_from_token(token)
        if not user_id:
            return False, "Invalid token"
        return True, user_id
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return False, "Authentication failed"


async def tool_executor(tool_name: str, tool_input: Dict[str, Any]) -> str:
    """
    Execute incident management tools.
    
    This is a bridge to the existing incident_tools module.
    In production, this should call the actual API endpoints.
    """
    from incident_tools import (
        _get_incidents_by_time_impl,
        _get_incidents_by_id_impl,
        _get_incident_stats_impl,
    )
    
    logger.info(f"🔧 Executing tool: {tool_name} with input: {tool_input}")
    
    try:
        if tool_name == "get_incidents":
            # Map to existing implementation
            result = await _get_incidents_by_time_impl({
                "status": tool_input.get("status"),
                "limit": tool_input.get("limit", 10),
                "time_range": "24h"
            })
            return json.dumps(result, indent=2, default=str)
        
        elif tool_name == "get_incident_details":
            result = await _get_incidents_by_id_impl({
                "incident_id": tool_input.get("incident_id")
            })
            return json.dumps(result, indent=2, default=str)
        
        elif tool_name == "get_incident_stats":
            result = await _get_incident_stats_impl({
                "time_range": tool_input.get("time_range", "24h")
            })
            return json.dumps(result, indent=2, default=str)
        
        elif tool_name == "acknowledge_incident":
            # This would call the actual API
            return json.dumps({
                "status": "success",
                "message": f"Incident {tool_input.get('incident_id')} acknowledged",
                "note": tool_input.get("note", "")
            })
        
        elif tool_name == "resolve_incident":
            # This would call the actual API
            return json.dumps({
                "status": "success", 
                "message": f"Incident {tool_input.get('incident_id')} resolved",
                "resolution": tool_input.get("resolution", "")
            })
        
        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
            
    except Exception as e:
        logger.error(f"Tool execution error: {e}", exc_info=True)
        return json.dumps({"error": str(e)})


@router.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """
    WebSocket endpoint for token-level streaming.
    
    Protocol:
    1. Client connects with ?token=JWT
    2. Client sends: {"prompt": "...", "session_id": "..."}
    3. Server streams: {"type": "delta", "content": "token"}
    4. Server sends: {"type": "complete"} when done
    
    Special messages:
    - {"type": "interrupt"} - Stop current generation
    - {"type": "clear_history"} - Clear conversation history
    """
    # Get token from query params
    token = websocket.query_params.get("token")
    
    # Verify authentication
    is_valid, result = await verify_token(token)
    if not is_valid:
        logger.warning(f"🚫 Streaming WebSocket auth failed: {result}")
        await websocket.close(code=4001, reason="Unauthorized")
        return
    
    user_id = result
    await websocket.accept()
    logger.info(f"✅ Streaming WebSocket connected for user: {user_id}")
    
    # Generate session ID
    session_id = str(uuid.uuid4())
    
    # Create streaming agent for this session
    agent = create_streaming_agent(include_tools=True)
    active_sessions[session_id] = agent
    
    # Send session info to client
    await websocket.send_json({
        "type": "session_created",
        "session_id": session_id,
        "message": "Streaming session established"
    })
    
    # Output queue for streaming events
    output_queue: asyncio.Queue = asyncio.Queue()
    
    # Task references
    stream_task = None
    sender_task = None
    
    async def send_events():
        """Send events from output queue to WebSocket."""
        try:
            while True:
                event = await output_queue.get()
                if event is None:
                    break
                await websocket.send_json(event)
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected during send")
        except Exception as e:
            logger.error(f"Send error: {e}")
    
    try:
        # Start sender task
        sender_task = asyncio.create_task(send_events())
        
        while True:
            try:
                # Receive message from client
                raw_message = await websocket.receive_text()
                message = json.loads(raw_message)
                
                msg_type = message.get("type", "chat")
                
                # Handle interrupt
                if msg_type == "interrupt":
                    logger.info("🛑 Interrupt requested")
                    agent.interrupt()
                    if stream_task and not stream_task.done():
                        stream_task.cancel()
                        try:
                            await stream_task
                        except asyncio.CancelledError:
                            pass
                    await websocket.send_json({"type": "interrupted"})
                    continue
                
                # Handle clear history
                if msg_type == "clear_history":
                    agent.clear_history()
                    await websocket.send_json({
                        "type": "history_cleared",
                        "message": "Conversation history cleared"
                    })
                    continue
                
                # Handle chat message
                prompt = message.get("prompt", "")
                if not prompt:
                    await websocket.send_json({
                        "type": "error",
                        "error": "Empty prompt"
                    })
                    continue
                
                logger.info(f"📨 Received prompt: {prompt[:50]}...")
                
                # Cancel any existing stream task
                if stream_task and not stream_task.done():
                    stream_task.cancel()
                    try:
                        await stream_task
                    except asyncio.CancelledError:
                        pass
                
                # Start streaming response
                stream_task = asyncio.create_task(
                    agent.stream_response(
                        prompt=prompt,
                        output_queue=output_queue,
                        tool_executor=tool_executor
                    )
                )
                
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "error": "Invalid JSON message"
                })
            except WebSocketDisconnect:
                logger.info(f"🔌 WebSocket disconnected: {session_id}")
                break
                
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        # Cleanup
        if stream_task and not stream_task.done():
            stream_task.cancel()
        if sender_task and not sender_task.done():
            await output_queue.put(None)  # Signal sender to stop
            sender_task.cancel()
        
        # Remove session
        if session_id in active_sessions:
            del active_sessions[session_id]
        
        logger.info(f"🧹 Cleaned up session: {session_id}")


@router.get("/streaming/status")
async def streaming_status():
    """Get status of streaming service."""
    return {
        "status": "ok",
        "active_sessions": len(active_sessions),
        "tools_available": len(INCIDENT_TOOLS)
    }
