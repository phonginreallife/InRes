"""
Streaming WebSocket Routes for Token-level LLM Streaming.

This module provides WebSocket endpoints that stream tokens directly
from the Anthropic API to the frontend in real-time.

HYBRID APPROACH:
- Token streaming for text responses (fast UX)
- MCP tool support for user-configured integrations (Confluence, Coralogix, etc.)

INTEGRATIONS:
- Uses core.ToolExecutor for unified tool handling
- Uses core.ToolContext for mutable org/project context
- Audit logging for security and compliance
- Conversation history for message persistence and resume
"""

import asyncio
import json
import logging
import os
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

# Parent package imports (api/ai level)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from supabase_storage import extract_user_id_from_token, get_user_mcp_servers
from core.tool_executor import ToolExecutor, ToolContext, create_tool_executor

# Local package imports
from .agent import StreamingAgent, INCIDENT_TOOLS
from .mcp_client import MCPToolManager, get_mcp_pool

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


# Note: ToolContext and create_tool_executor are now imported from core.tool_executor
# This eliminates ~150 lines of duplicated tool execution code


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
    
    # Create unified tool executor using core module
    tool_executor = create_tool_executor(
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
