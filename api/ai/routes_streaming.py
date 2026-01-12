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

import httpx
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


def create_tool_executor(auth_token: str, org_id: str = None, project_id: str = None):
    """
    Create a tool executor function with the auth token and context captured.
    
    This makes HTTP calls to the backend API for proper authentication.
    """
    api_base = os.getenv("INRES_API_URL", "http://inres-api:8080")
    
    async def tool_executor(tool_name: str, tool_input: Dict[str, Any]) -> str:
        logger.debug(f"Executing tool: {tool_name} with input: {tool_input}")
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_token}",
        }
        # Add org/project context to headers for tenant isolation
        if org_id:
            headers["X-Org-ID"] = org_id
        if project_id:
            headers["X-Project-ID"] = project_id
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if tool_name == "get_incidents":
                    params = {"limit": tool_input.get("limit", 10)}
                    if tool_input.get("status"):
                        params["status"] = tool_input["status"]
                    
                    resp = await client.get(
                        f"{api_base}/incidents",
                        headers=headers,
                        params=params
                    )
                    logger.debug(f"get_incidents response: {resp.status_code}")
                    if resp.status_code == 200:
                        data = resp.json()
                        return json.dumps(data, indent=2, default=str)
                    return json.dumps({"error": f"API error: {resp.status_code}", "body": resp.text})
                
                elif tool_name == "get_incident_details":
                    incident_id = tool_input.get("incident_id")
                    resp = await client.get(
                        f"{api_base}/incidents/{incident_id}",
                        headers=headers
                    )
                    logger.debug(f"get_incident_details response: {resp.status_code}")
                    if resp.status_code == 200:
                        return json.dumps(resp.json(), indent=2, default=str)
                    return json.dumps({"error": f"Incident not found: {incident_id}", "status": resp.status_code})
                
                elif tool_name == "get_incident_stats":
                    time_range = tool_input.get("time_range", "24h")
                    # Try the stats endpoint
                    resp = await client.get(
                        f"{api_base}/incidents/stats",
                        headers=headers,
                        params={"range": time_range}
                    )
                    logger.debug(f"get_incident_stats response: {resp.status_code}")
                    if resp.status_code == 200:
                        return json.dumps(resp.json(), indent=2, default=str)
                    # Fallback: get incidents and calculate stats
                    resp = await client.get(
                        f"{api_base}/incidents",
                        headers=headers,
                        params={"limit": 100}
                    )
                    logger.debug(f"get_incident_stats response: {resp.status_code}")
                    if resp.status_code == 200:
                        incidents = resp.json()
                        # Calculate basic stats
                        if isinstance(incidents, list):
                            total = len(incidents)
                            by_status = {}
                            by_severity = {}
                            for inc in incidents:
                                status = inc.get("status", "unknown")
                                severity = inc.get("severity", "unknown")
                                by_status[status] = by_status.get(status, 0) + 1
                                by_severity[severity] = by_severity.get(severity, 0) + 1
                            return json.dumps({
                                "time_range": time_range,
                                "total_incidents": total,
                                "by_status": by_status,
                                "by_severity": by_severity,
                            }, indent=2)
                    return json.dumps({"error": "Could not fetch incident stats"})
                
                elif tool_name == "acknowledge_incident":
                    incident_id = tool_input.get("incident_id")
                    resp = await client.post(
                        f"{api_base}/incidents/{incident_id}/acknowledge",
                        headers=headers,
                        json={"note": tool_input.get("note", "")}
                    )
                    if resp.status_code == 200:
                        return json.dumps({"status": "success", "message": f"Incident {incident_id} acknowledged"})
                    return json.dumps({"error": f"Failed to acknowledge: {resp.status_code}"})
                
                elif tool_name == "resolve_incident":
                    incident_id = tool_input.get("incident_id")
                    resp = await client.post(
                        f"{api_base}/incidents/{incident_id}/resolve",
                        headers=headers,
                        json={"resolution": tool_input.get("resolution", "")}
                    )
                    if resp.status_code == 200:
                        return json.dumps({"status": "success", "message": f"Incident {incident_id} resolved"})
                    return json.dumps({"error": f"Failed to resolve: {resp.status_code}"})
                
                else:
                    return json.dumps({"error": f"Unknown tool: {tool_name}"})
                    
        except httpx.TimeoutException:
            logger.error(f"Tool {tool_name} timed out")
            return json.dumps({"error": f"Tool {tool_name} timed out"})
        except Exception as e:
            logger.error(f"Tool execution error: {e}", exc_info=True)
            return json.dumps({"error": str(e)})
    
    return tool_executor


@router.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """
    WebSocket endpoint for token-level streaming.
    
    Protocol:
    1. Client connects with ?token=JWT
    2. Client sends: {"prompt": "...", "session_id": "..."}
    3. Server streams: {"type": "delta", "content": "token"}
    4. Server sends: {"type": "complete"} when done
    """
    # Get token and context from query params
    token = websocket.query_params.get("token")
    org_id = websocket.query_params.get("org_id")
    project_id = websocket.query_params.get("project_id")
    
    # Verify authentication
    is_valid, result = await verify_token(token)
    if not is_valid:
        logger.warning(f"🚫 Streaming WebSocket auth failed: {result}")
        await websocket.close(code=4001, reason="Unauthorized")
        return
    
    user_id = result
    await websocket.accept()
    logger.info(f"✅ Streaming WebSocket connected for user: {user_id}, org: {org_id}")
    
    # Generate session ID
    session_id = str(uuid.uuid4())
    
    # Create streaming agent for this session
    agent = create_streaming_agent(include_tools=True)
    active_sessions[session_id] = agent
    
    # Create tool executor with auth token and org context
    tool_executor = create_tool_executor(token, org_id, project_id)
    
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
