"""
Hybrid Agent WebSocket Routes.

Provides WebSocket endpoints for the hybrid agent that combines:
- SDK orchestration for planning and tool execution
- Token-level streaming for smooth UI experience

This is an alternative to the pure streaming routes, offering
better tool orchestration while maintaining token-level output.
"""

import asyncio
import json
import logging
import uuid
from typing import Any, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

# Parent package imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from supabase_storage import extract_user_id_from_token, get_user_mcp_servers
from core.tool_executor import ToolExecutor, ToolContext, create_tool_executor

# Local imports
from .agent import HybridAgent, HybridAgentConfig
from streaming.agent import INCIDENT_TOOLS
from streaming.mcp_client import MCPToolManager, get_mcp_pool

# Audit and conversation history
from audit_service import get_audit_service
from routes_conversations import save_conversation, save_message, update_conversation_activity

# Redis session store
from utils.redis_client import get_session_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hybrid", tags=["hybrid"])

# Active sessions (local to this instance)
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


@router.websocket("/ws/stream")
async def websocket_hybrid_stream(websocket: WebSocket):
    """
    Hybrid WebSocket endpoint with SDK orchestration + token streaming.
    
    Protocol:
    1. Client connects with ?token=JWT
    2. Server loads MCP servers, creates hybrid agent
    3. Client sends: {"prompt": "...", "session_id": "..."}
    4. Server streams: {"type": "delta", "content": "token"}
    5. Server may send tool events during processing
    6. Server sends: {"type": "complete"} when done
    
    Advantages over pure streaming:
    - Better tool planning (SDK orchestration)
    - MCP server support with full SDK features
    - Permission callbacks for tool execution
    
    Advantages over pure SDK:
    - Token-level streaming (smooth UX)
    - Lower latency for simple responses
    """
    # Get auth from query params
    token = websocket.query_params.get("token")
    org_id = websocket.query_params.get("org_id")
    project_id = websocket.query_params.get("project_id")
    
    audit = get_audit_service()
    client_ip = websocket.client.host if websocket.client else None
    
    # Verify authentication
    is_valid, result = await verify_token(token)
    if not is_valid:
        logger.warning(f"Hybrid WebSocket auth failed: {result}")
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
    logger.info(f"Hybrid WebSocket connected for user: {user_id}, org: {org_id}")
    
    # Generate session ID
    session_id = str(uuid.uuid4())
    
    # Initialize MCP tool manager
    mcp_manager = None
    mcp_tools = []
    
    try:
        # Load user's MCP servers
        logger.info(f"Loading MCP servers for hybrid agent: user={user_id}")
        user_mcp_config = await get_user_mcp_servers(auth_token=token, user_id=user_id)
        
        if user_mcp_config:
            logger.info(f"Found {len(user_mcp_config)} MCP server configs")
            pool = await get_mcp_pool()
            mcp_manager = await pool.get_servers_for_user(user_id, user_mcp_config)
            mcp_tools = mcp_manager.get_all_tools()
            logger.info(f"Loaded {len(mcp_tools)} MCP tools")
        else:
            logger.info("No MCP servers configured")
            mcp_manager = MCPToolManager()
            
    except Exception as e:
        logger.error(f"Failed to load MCP servers: {e}", exc_info=True)
        mcp_manager = MCPToolManager()
    
    # Combine built-in and MCP tools
    all_tools = INCIDENT_TOOLS.copy()
    all_tools.extend(mcp_tools)
    
    # Create hybrid agent config
    config = HybridAgentConfig(
        model="claude-sonnet-4-20250514",
        streaming_model="claude-sonnet-4-20250514",
        planning_model="claude-sonnet-4-20250514",
        max_tokens=4096,
        max_planning_tokens=1024,
        tools=all_tools,
        mcp_servers={},  # MCP handled by tool executor
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
- Use Coralogix MCP tools for querying logs
- Use Confluence MCP tools for documentation
- Use other MCP tools for their respective services

Be concise but thorough in your responses."""
    )
    
    # Create hybrid agent
    agent = HybridAgent(config=config)
    
    # Store session
    active_sessions[session_id] = {
        "agent": agent,
        "mcp_manager": mcp_manager,
        "user_id": user_id,
        "is_first_message": True,
        "conversation_id": session_id
    }
    
    # Register in Redis
    session_store = get_session_store()
    await session_store.register(
        session_id=session_id,
        user_id=user_id,
        metadata={
            "org_id": org_id,
            "project_id": project_id,
            "mcp_servers": mcp_manager.server_count if mcp_manager else 0,
            "agent_type": "hybrid",
            "client_ip": client_ip
        }
    )
    
    # Create tool context and executor
    tool_context = ToolContext(org_id=org_id, project_id=project_id)
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
    
    # Send session info
    await websocket.send_json({
        "type": "session_created",
        "session_id": session_id,
        "conversation_id": session_id,
        "agent_type": "hybrid",
        "message": "Hybrid agent session established",
        "mcp_servers": mcp_manager.server_count if mcp_manager else 0,
        "total_tools": len(all_tools)
    })
    
    session = active_sessions[session_id]
    output_queue: asyncio.Queue = asyncio.Queue()
    
    # Task references
    stream_task = None
    sender_task = None
    
    async def send_events():
        """Send events from queue to WebSocket."""
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
        sender_task = asyncio.create_task(send_events())
        
        while True:
            try:
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
                
                # Update context if provided
                msg_org_id = message.get("org_id")
                msg_project_id = message.get("project_id")
                if msg_org_id or msg_project_id:
                    tool_context.update(org_id=msg_org_id, project_id=msg_project_id)
                
                logger.info(f"Hybrid agent processing: {prompt[:50]}...")
                
                # Audit: log chat message
                await audit.log_chat_message(
                    user_id=user_id,
                    session_id=session_id,
                    message_preview=prompt[:100],
                    org_id=tool_context.org_id,
                    project_id=tool_context.project_id
                )
                
                # Save conversation on first message
                if session["is_first_message"]:
                    await save_conversation(
                        user_id=user_id,
                        conversation_id=session["conversation_id"],
                        first_message=prompt,
                        model="claude-sonnet-4-hybrid",
                        metadata={
                            "org_id": tool_context.org_id,
                            "project_id": tool_context.project_id,
                            "mode": "hybrid"
                        }
                    )
                    session["is_first_message"] = False
                
                # Save user message
                await save_message(
                    conversation_id=session["conversation_id"],
                    role="user",
                    content=prompt
                )
                
                # Cancel existing stream task
                if stream_task and not stream_task.done():
                    stream_task.cancel()
                    try:
                        await stream_task
                    except asyncio.CancelledError:
                        pass
                
                # Start hybrid processing
                conv_id = session["conversation_id"]
                
                async def process_and_save():
                    """Process with hybrid agent and save response."""
                    response = await agent.process_message(
                        prompt=prompt,
                        output_queue=output_queue,
                        tool_executor=tool_executor
                    )
                    
                    if response:
                        await save_message(
                            conversation_id=conv_id,
                            role="assistant",
                            content=response
                        )
                        await update_conversation_activity(conv_id)
                    
                    return response
                
                stream_task = asyncio.create_task(process_and_save())
                
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "error": "Invalid JSON message"
                })
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected: {session_id}")
                break
                
    except Exception as e:
        logger.error(f"Hybrid WebSocket error: {e}", exc_info=True)
    finally:
        # Cleanup
        logger.info(f"Cleaning up hybrid session: {session_id}")
        
        if stream_task and not stream_task.done():
            stream_task.cancel()
        if sender_task and not sender_task.done():
            await output_queue.put(None)
            sender_task.cancel()
        
        # Release MCP servers
        try:
            pool = await get_mcp_pool()
            await pool.release_servers_for_user(user_id)
        except Exception as e:
            logger.error(f"Failed to release MCP servers: {e}")
        
        # Remove session
        if session_id in active_sessions:
            del active_sessions[session_id]
        
        # Unregister from Redis
        try:
            session_store = get_session_store()
            await session_store.unregister(session_id)
        except Exception as e:
            logger.error(f"Failed to unregister session: {e}")
        
        logger.info(f"Hybrid session cleanup complete: {session_id}")


@router.get("/status")
async def hybrid_status():
    """Get status of hybrid agent service."""
    try:
        pool = await get_mcp_pool()
        pool_stats = pool.stats
    except Exception:
        pool_stats = {"error": "Pool not initialized"}
    
    try:
        session_store = get_session_store()
        redis_stats = await session_store.get_stats()
    except Exception as e:
        redis_stats = {"error": str(e)}
    
    return {
        "status": "ok",
        "agent_type": "hybrid",
        "local_sessions": len(active_sessions),
        "builtin_tools": len(INCIDENT_TOOLS),
        "pool": pool_stats,
        "redis": redis_stats
    }
