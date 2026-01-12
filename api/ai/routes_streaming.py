"""
Streaming WebSocket Routes for Token-level LLM Streaming.

This module provides WebSocket endpoints that stream tokens directly
from the Anthropic API to the frontend in real-time.

HYBRID APPROACH:
- Token streaming for text responses (fast UX)
- MCP tool support for user-configured integrations (Confluence, Coralogix, etc.)

INTEGRATIONS:
- Audit logging for security and compliance
- Conversation history for message persistence and resume
"""

import asyncio
import json
import logging
import os
import uuid
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from supabase_storage import extract_user_id_from_token, get_user_mcp_servers

from streaming_agent import StreamingAgent, INCIDENT_TOOLS
from mcp_streaming_client import MCPToolManager, get_mcp_pool

# Audit and conversation history integration
from audit_service import get_audit_service, EventType
from routes_conversations import save_conversation, save_message, update_conversation_activity

logger = logging.getLogger(__name__)

router = APIRouter()

# Store active streaming sessions with their MCP managers
active_sessions: Dict[str, Dict[str, Any]] = {}


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


class ToolContext:
    """Mutable context for tool execution that can be updated per message."""
    def __init__(self, org_id: str = None, project_id: str = None):
        self.org_id = org_id
        self.project_id = project_id
    
    def update(self, org_id: str = None, project_id: str = None):
        """Update context with new values (only if provided)."""
        if org_id:
            self.org_id = org_id
        if project_id:
            self.project_id = project_id


def create_hybrid_tool_executor(
    auth_token: str,
    context: ToolContext,
    mcp_manager: Optional[MCPToolManager] = None,
    user_id: str = None,
    session_id: str = None
):
    """
    Create a hybrid tool executor that handles both built-in and MCP tools.
    
    - Built-in tools (get_incidents, etc.): HTTP calls to backend API
    - MCP tools (mcp__*): Routed to MCP servers via subprocess
    
    The context object is mutable and can be updated per message to support
    dynamic org_id/project_id from the message body.
    
    Includes audit logging for all tool executions.
    """
    api_base = os.getenv("INRES_API_URL", "http://inres-api:8080")
    audit = get_audit_service()
    
    async def tool_executor(tool_name: str, tool_input: Dict[str, Any]) -> str:
        logger.info(f"Executing tool: {tool_name} with context org_id={context.org_id}, project_id={context.project_id}")
        
        # Audit: log tool execution start
        request_id = str(uuid.uuid4())
        if user_id and session_id:
            await audit.log_tool_requested(
                user_id=user_id,
                session_id=session_id,
                tool_name=tool_name,
                tool_input=tool_input,
                request_id=request_id
            )
        
        # Route MCP tools to MCP manager
        if tool_name.startswith("mcp__") and mcp_manager:
            logger.info(f"Routing to MCP: {tool_name}")
            return await mcp_manager.call_tool(tool_name, tool_input)
        
        # Built-in tools via HTTP
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_token}",
        }
        if context.org_id:
            headers["X-Org-ID"] = context.org_id
        if context.project_id:
            headers["X-Project-ID"] = context.project_id
        
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
                    if resp.status_code == 200:
                        return json.dumps(resp.json(), indent=2, default=str)
                    return json.dumps({"error": f"API error: {resp.status_code}"})
                
                elif tool_name == "get_incident_details":
                    incident_id = tool_input.get("incident_id")
                    logger.info(f"Fetching incident {incident_id} with headers: X-Org-ID={headers.get('X-Org-ID')}, X-Project-ID={headers.get('X-Project-ID')}")
                    resp = await client.get(
                        f"{api_base}/incidents/{incident_id}",
                        headers=headers
                    )
                    if resp.status_code == 200:
                        return json.dumps(resp.json(), indent=2, default=str)
                    # Log full error for debugging
                    error_body = resp.text
                    logger.error(f"Failed to fetch incident {incident_id}: status={resp.status_code}, body={error_body}")
                    return json.dumps({
                        "error": f"Incident not found: {incident_id}",
                        "status_code": resp.status_code,
                        "details": error_body[:500] if error_body else None
                    })
                
                elif tool_name == "get_incident_stats":
                    time_range = tool_input.get("time_range", "24h")
                    resp = await client.get(
                        f"{api_base}/incidents/stats",
                        headers=headers,
                        params={"range": time_range}
                    )
                    if resp.status_code == 200:
                        return json.dumps(resp.json(), indent=2, default=str)
                    # Fallback: calculate from incidents
                    resp = await client.get(
                        f"{api_base}/incidents",
                        headers=headers,
                        params={"limit": 100}
                    )
                    if resp.status_code == 200:
                        incidents = resp.json()
                        if isinstance(incidents, list):
                            by_status = {}
                            by_severity = {}
                            for inc in incidents:
                                status = inc.get("status", "unknown")
                                severity = inc.get("severity", "unknown")
                                by_status[status] = by_status.get(status, 0) + 1
                                by_severity[severity] = by_severity.get(severity, 0) + 1
                            return json.dumps({
                                "time_range": time_range,
                                "total_incidents": len(incidents),
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
    WebSocket endpoint for token-level streaming with MCP support.
    
    Protocol:
    1. Client connects with ?token=JWT
    2. Server loads user's MCP servers and sends session info
    3. Client sends: {"prompt": "...", "session_id": "..."}
    4. Server streams: {"type": "delta", "content": "token"}
    5. Server sends: {"type": "complete"} when done
    
    MCP Integration:
    - User's MCP servers are loaded from database
    - MCP tools are available alongside built-in tools
    - Tool calls are routed appropriately (HTTP or MCP protocol)
    """
    # Get token and context from query params
    token = websocket.query_params.get("token")
    org_id = websocket.query_params.get("org_id")
    project_id = websocket.query_params.get("project_id")
    
    # Get audit service
    audit = get_audit_service()
    client_ip = websocket.client.host if websocket.client else None
    
    # Verify authentication
    is_valid, result = await verify_token(token)
    if not is_valid:
        logger.warning(f"Streaming WebSocket auth failed: {result}")
        # Audit: log auth failure
        await audit.log_auth_failed(
            user_id=None,
            error_code="INVALID_TOKEN",
            error_message=result,
            source_ip=client_ip,
            org_id=org_id
        )
        await websocket.close(code=4001, reason="Unauthorized")
        return
    
    user_id = result
    await websocket.accept()
    logger.info(f"Streaming WebSocket connected for user: {user_id}, org: {org_id}")
    
    # Generate session ID
    session_id = str(uuid.uuid4())
    
    # Initialize MCP tool manager using connection pool
    mcp_manager = None
    mcp_tools = []
    use_pool = True  # Use pooled connections for scalability
    
    try:
        # Load user's MCP servers from database
        logger.info(f"Loading MCP servers for user: {user_id}")
        user_mcp_config = await get_user_mcp_servers(auth_token=token, user_id=user_id)
        
        if user_mcp_config:
            logger.info(f"Found {len(user_mcp_config)} MCP server configs")
            
            if use_pool:
                # Use global pool for scalability (shared servers across sessions)
                pool = await get_mcp_pool()
                mcp_manager = await pool.get_servers_for_user(user_id, user_mcp_config)
                logger.info(f"Pool stats: {pool.stats}")
            else:
                # Per-session mode (isolated but resource-heavy)
                mcp_manager = MCPToolManager()
                await mcp_manager.add_servers_from_config(user_mcp_config)
            
            # Get tools from MCP servers
            mcp_tools = mcp_manager.get_all_tools()
            logger.info(f"Loaded {len(mcp_tools)} MCP tools: {[t['name'] for t in mcp_tools]}")
        else:
            logger.info("No MCP servers configured for user")
            mcp_manager = MCPToolManager()  # Empty manager
            
    except Exception as e:
        logger.error(f"Failed to load MCP servers: {e}", exc_info=True)
        mcp_manager = MCPToolManager()  # Fallback to empty manager
    
    # Combine built-in tools with MCP tools
    all_tools = INCIDENT_TOOLS.copy()
    all_tools.extend(mcp_tools)
    
    # Create streaming agent with all tools
    agent = StreamingAgent(
        tools=all_tools,
        system_prompt="""You are an AI assistant specialized in incident response and DevOps.
You help users manage incidents, analyze alerts, and troubleshoot issues.

## Tool Selection Guidelines

**For InRes Incident Operations (ALWAYS use built-in tools):**
- Use `get_incidents` to list incidents from InRes
- Use `get_incident_details` to fetch a specific incident by its InRes UUID
- Use `acknowledge_incident` to acknowledge an InRes incident
- Use `resolve_incident` to resolve an InRes incident
- Use `get_incident_stats` for incident statistics

**For External Integrations (MCP tools prefixed with mcp__):**
- Use Coralogix MCP tools for querying logs, searching logs, or log-based investigation
- Use Confluence MCP tools for documentation lookup
- Use other MCP tools for their respective external services

**Important:** InRes incident UUIDs (like 1393de28-1916-4f9f-bc2f-36e990a21967) should ONLY be used with built-in InRes tools (get_incident_details, acknowledge_incident, resolve_incident). Do NOT pass InRes UUIDs to external MCP tools like Coralogix.

Be concise but thorough in your responses."""
    )
    
    # Store session info (including conversation tracking state)
    active_sessions[session_id] = {
        "agent": agent,
        "mcp_manager": mcp_manager,
        "user_id": user_id,
        "is_first_message": True,  # Track if first message for conversation creation
        "conversation_id": session_id  # Use session_id as conversation_id
    }
    
    # Create mutable tool context (can be updated per message)
    tool_context = ToolContext(org_id=org_id, project_id=project_id)
    
    # Create hybrid tool executor with mutable context and audit support
    tool_executor = create_hybrid_tool_executor(
        auth_token=token,
        context=tool_context,
        mcp_manager=mcp_manager,
        user_id=user_id,
        session_id=session_id
    )
    
    # Audit: log session created
    await audit.log_session_created(
        user_id=user_id,
        session_id=session_id,
        source_ip=client_ip,
        user_agent=websocket.headers.get("user-agent"),
        org_id=org_id,
        project_id=project_id
    )
    
    # Send session info to client
    await websocket.send_json({
        "type": "session_created",
        "session_id": session_id,
        "conversation_id": session_id,  # Send conversation_id to client for resume support
        "message": "Streaming session established",
        "mcp_servers": mcp_manager.server_count,
        "total_tools": len(all_tools)
    })
    
    # Reference to session for mutable state tracking
    session = active_sessions[session_id]
    
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
                    logger.info("Interrupt requested")
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
                
                # Update context with org_id/project_id from message body (if provided)
                # This allows the frontend to send context per message
                msg_org_id = message.get("org_id")
                msg_project_id = message.get("project_id")
                if msg_org_id or msg_project_id:
                    tool_context.update(org_id=msg_org_id, project_id=msg_project_id)
                    logger.info(f"Updated tool context: org_id={tool_context.org_id}, project_id={tool_context.project_id}")
                
                logger.info(f"Received prompt: {prompt[:50]}...")
                
                # Audit: log chat message
                await audit.log_chat_message(
                    user_id=user_id,
                    session_id=session_id,
                    message_preview=prompt[:100],
                    org_id=tool_context.org_id,
                    project_id=tool_context.project_id
                )
                
                # Conversation history: save conversation on first message
                if session["is_first_message"]:
                    await save_conversation(
                        user_id=user_id,
                        conversation_id=session["conversation_id"],
                        first_message=prompt,
                        model="claude-sonnet-4-streaming",
                        metadata={
                            "org_id": tool_context.org_id,
                            "project_id": tool_context.project_id,
                            "mode": "streaming"
                        }
                    )
                    session["is_first_message"] = False
                
                # Save user message to conversation history
                await save_message(
                    conversation_id=session["conversation_id"],
                    role="user",
                    content=prompt
                )
                
                # Cancel any existing stream task
                if stream_task and not stream_task.done():
                    stream_task.cancel()
                    try:
                        await stream_task
                    except asyncio.CancelledError:
                        pass
                
                # Start streaming response with history tracking
                conv_id = session["conversation_id"]  # Capture for closure
                
                async def stream_and_save():
                    """Stream response and save to conversation history."""
                    response = await agent.stream_response(
                        prompt=prompt,
                        output_queue=output_queue,
                        tool_executor=tool_executor
                    )
                    # Save assistant response to conversation history
                    if response:
                        await save_message(
                            conversation_id=conv_id,
                            role="assistant",
                            content=response
                        )
                        # Update conversation activity
                        await update_conversation_activity(conv_id)
                    return response
                
                stream_task = asyncio.create_task(stream_and_save())
                
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "error": "Invalid JSON message"
                })
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected: {session_id}")
                break
                
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        # Cleanup
        logger.info(f"Cleaning up session: {session_id}")
        
        if stream_task and not stream_task.done():
            stream_task.cancel()
        if sender_task and not sender_task.done():
            await output_queue.put(None)
            sender_task.cancel()
        
        # Release MCP servers (pool handles actual cleanup)
        if use_pool:
            try:
                pool = await get_mcp_pool()
                await pool.release_servers_for_user(user_id)
            except Exception as e:
                logger.error(f"Failed to release pooled servers: {e}")
        elif mcp_manager:
            await mcp_manager.shutdown()
        
        # Remove session
        if session_id in active_sessions:
            del active_sessions[session_id]
        
        logger.info(f"Session cleanup complete: {session_id}")


@router.get("/streaming/status")
async def streaming_status():
    """Get status of streaming service including pool statistics."""
    try:
        pool = await get_mcp_pool()
        pool_stats = pool.stats
    except Exception:
        pool_stats = {"error": "Pool not initialized"}
    
    return {
        "status": "ok",
        "active_sessions": len(active_sessions),
        "builtin_tools": len(INCIDENT_TOOLS),
        "pool": pool_stats
    }
