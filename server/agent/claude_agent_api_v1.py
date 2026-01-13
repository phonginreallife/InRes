"""
Claude Agent API v1 - Production Hybrid Agent.

This module provides the main WebSocket API using the HybridAgent that combines:
- SDK-style orchestration for planning and tool management
- Token-level streaming for smooth UI experience
- Full MCP server support

The hybrid approach provides the best of both worlds:
- Fast token-by-token streaming (like direct API)
- Smart tool orchestration (like Claude Agent SDK)
"""

import asyncio
import json
import logging
import os
import time
import uuid
from pathlib import Path

# Load config from YAML (unifies config with Go API)
from config import loader as config_loader
config_loader.load_config()

from asyncio import Lock
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Import from organized packages
from tools import create_incident_tools_server, set_auth_token, set_org_id, set_project_id
from security import get_verifier, init_verifier
from audit import (
    get_audit_service,
    init_audit_service,
    shutdown_audit_service,
    EventType,
    EventStatus,
    build_hooks_config,
)
from services import (
    extract_user_id_from_token,
    get_user_mcp_servers,
    get_user_workspace_path,
    load_user_plugins,
    sync_mcp_config_to_local,
    sync_memory_to_workspace,
    sync_user_skills,
    unzip_installed_plugins,
    get_user_allowed_tools,
    add_user_allowed_tool,
    delete_user_allowed_tool,
    start_pgmq_consumer,
    stop_pgmq_consumer,
)
from utils import execute_query

# Import routers from routes package
from routes import (
    db_router,
    conversations_router,
    audit_router,
    sync_router,
    mcp_router,
    tools_router,
    memory_router,
    marketplace_router,
    save_conversation,
    save_message,
    update_conversation_activity,
)
from routes.sync import set_mcp_cache

# Import Hybrid Agent (production agent)
from hybrid import HybridAgent, HybridAgentConfig
from core.tool_executor import ToolExecutor, ToolContext, create_tool_executor
from streaming.agent import INCIDENT_TOOLS
from streaming.mcp_client import MCPToolManager, get_mcp_pool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Track tool usage for demonstration
tool_usage_log = []


def sanitize_error_message(error: Exception, context: str = "") -> str:
    """
    Sanitize error messages to prevent information disclosure.

    Returns a generic error message while logging full details.

    Args:
        error: The exception to sanitize
        context: Context string for logging (e.g., "syncing bucket", "creating session")

    Returns:
        Generic error message safe to return to client
    """
    # Log full error details for debugging
    logger.error(f"Error {context}: {type(error).__name__}: {str(error)}", exc_info=True)

    # Return generic message based on error type
    if isinstance(error, (ConnectionError, TimeoutError)):
        return "Service temporarily unavailable. Please try again."
    elif isinstance(error, PermissionError):
        return "Access denied. Please check your permissions."
    elif isinstance(error, ValueError):
        return "Invalid input provided. Please check your request."
    elif "auth" in str(error).lower() or "token" in str(error).lower():
        return "Authentication failed. Please verify your credentials."
    elif "database" in str(error).lower() or "postgres" in str(error).lower():
        return "Database error. Please contact support if this persists."
    else:
        return "An internal error occurred. Please contact support if this persists."


# ==========================================
# Rate Limiting (Redis-backed for horizontal scaling)
# ==========================================

from utils.redis_client import get_rate_limiter, get_session_store, close_redis

# Get rate limit config from environment
RATE_LIMIT_REQUESTS = int(os.getenv("AI_RATE_LIMIT", "60"))
RATE_LIMIT_WINDOW = 60  # seconds


async def check_rate_limit(user_id: str) -> bool:
    """
    Check if user has exceeded rate limit using Redis.

    Args:
        user_id: User identifier

    Returns:
        True if within rate limit, False if exceeded
    """
    rate_limiter = get_rate_limiter()
    return await rate_limiter.is_allowed(user_id)


async def rate_limit_middleware(request: Request, call_next):
    """
    Rate limiting middleware for all API endpoints.

    Uses Redis-backed rate limiting for horizontal scaling.
    Limits requests per user based on AI_RATE_LIMIT environment variable.
    """
    # Skip rate limiting for health check
    if request.url.path == "/health":
        return await call_next(request)

    # Extract user_id from token
    auth_token = (
        request.query_params.get("auth_token")
        or request.headers.get("authorization", "")
    )

    if auth_token:
        user_id = extract_user_id_from_token(auth_token)
        if user_id:
            # Check rate limit using Redis
            if not await check_rate_limit(user_id):
                # Log rate limit event
                audit = get_audit_service()
                await audit.log_security_event(
                    event_type=EventType.AUTH_RATE_LIMITED,
                    user_id=user_id,
                    action="rate_limit_check",
                    error_code="RATE_LIMIT_EXCEEDED",
                    error_message=f"Exceeded {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW}s",
                    source_ip=request.client.host if request.client else None,
                    metadata={"path": str(request.url.path)}
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "error": "Rate limit exceeded. Please try again later.",
                        "retry_after": RATE_LIMIT_WINDOW,
                    },
                )

    return await call_next(request)


# Background worker task reference
cleanup_worker_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting application...")

    # Initialize audit service
    await init_audit_service()
    logger.info("📝 Audit service initialized")

    # Start PGMQ consumer for incident analytics
    await start_pgmq_consumer()
    logger.info("🤖 Incident analytics PGMQ consumer started")

    # No background workers needed anymore:
    # - heartbeat_task is per-connection (called in websocket endpoint)
    # - marketplace cleanup is now synchronous (no worker needed)

    logger.info("Application started")

    yield

    # Shutdown
    logger.info("🛑 Stopping application...")

    # Stop PGMQ consumer
    await stop_pgmq_consumer()
    logger.info("🤖 Incident analytics PGMQ consumer stopped")

    # Close Redis connection
    await close_redis()
    logger.info("🔴 Redis connection closed")

    # Shutdown audit service (flush remaining events)
    await shutdown_audit_service()
    logger.info("📝 Audit service stopped")

    logger.info("Application stopped")


app = FastAPI(
    title="Claude Agent API",
    description="WebSocket API for Claude Agent SDK with session management",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS middleware - Configure allowed origins from environment
# For development: use specific localhost domains
# For production: MUST use specific domains only (never use "*")
# SECURITY: Using "*" with allow_credentials=True is a security vulnerability
ALLOWED_ORIGINS = os.getenv(
    "AI_ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:8000"
).split(",")

# Strip whitespace from origins
ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS if origin.strip()]

logger.info(f"CORS configured with allowed origins: {ALLOWED_ORIGINS}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Apply rate limiting middleware
app.middleware("http")(rate_limit_middleware)
logger.info(f"[Rate Limiting]Enabled: {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW} seconds")

# Include database routes (installed_plugins, marketplaces)
app.include_router(db_router)
logger.info("[Database] Database routes loaded from routes_db.py")

# Include conversation history routes
app.include_router(conversations_router)
logger.info("[Conversation] Conversation routes loaded from routes_conversations.py")

# Include audit routes
app.include_router(audit_router)
logger.info("[Audit] Audit routes loaded from routes_audit.py")

# Include modular routes
app.include_router(sync_router)
logger.info("[Sync] Sync routes loaded from routes_sync.py")

app.include_router(mcp_router)
logger.info("[MCP] MCP routes loaded from routes_mcp.py")

app.include_router(tools_router)
logger.info("[Tools] Tools routes loaded from routes_tools.py")

app.include_router(memory_router)
logger.info("[Memory] Memory routes loaded from routes_memory.py")

app.include_router(marketplace_router)
logger.info("[Marketplace] Marketplace routes loaded from routes_marketplace.py")

# Hybrid agent is now the main /ws/chat endpoint (no separate routes needed)
logger.info("[Hybrid] HybridAgent is the production agent (SDK orchestration + token streaming)")

# In-memory cache for user MCP configs
# Simple dict cache - cleared on restart
user_mcp_cache: Dict[str, Dict[str, Any]] = {}

# Share cache with sync routes
set_mcp_cache(user_mcp_cache)

# Per-user locks for plugin installation (prevents race conditions)
# Key: user_id, Value: asyncio.Lock
user_plugin_locks: Dict[str, Lock] = {}


# Legacy SDK agent functions removed - now using HybridAgent


# API routes moved to separate files (routes_*.py)

async def marketplace_cleanup_worker():
    """
    Background worker to poll PGMQ for marketplace cleanup tasks.

    This worker runs continuously in the background and:
    1. Polls marketplace_cleanup_queue every 5 seconds
    2. Processes cleanup tasks
    3. Archives completed tasks
    4. Retries failed tasks (PGMQ handles this automatically)

    The worker uses PGMQ visibility timeout to prevent duplicate processing.
    """
    import psycopg2
    import psycopg2.extras
    from routes_marketplace import cleanup_marketplace_task

    logger.info("Marketplace cleanup worker started")

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not configured, worker cannot start")
        return

    # Create connection pool for efficiency
    conn = None

    while True:
        try:
            # Reconnect if needed
            if conn is None or conn.closed:
                conn = psycopg2.connect(db_url)
                logger.info("  Connected to PostgreSQL for PGMQ worker")

            # Read message from PGMQ
            # pgmq.read(queue_name => TEXT, vt => INTEGER, qty => INTEGER)
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT * FROM pgmq.read(
                        queue_name => %s,
                        vt => %s,
                        qty => %s
                    )
                    """,
                    ("marketplace_cleanup_queue", 300, 1),  # 5 min visibility timeout
                )
                messages = cur.fetchall()

            if not messages or len(messages) == 0:
                # No messages, sleep and retry
                await asyncio.sleep(5)
                continue

            # Process first message
            message = messages[0]
            msg_id = message["msg_id"]
            message_body = message["message"]  # Already parsed as dict by RealDictCursor

            logger.info(
                f"📬 Received cleanup task (msg_id: {msg_id}): {message_body}"
            )

            # Parse message
            user_id = message_body.get("user_id")
            marketplace_name = message_body.get("marketplace_name")
            marketplace_id = message_body.get("marketplace_id")
            zip_path = message_body.get("zip_path")

            # Execute cleanup
            cleanup_result = await cleanup_marketplace_task(
                user_id, marketplace_name, marketplace_id, zip_path
            )

            if cleanup_result["success"]:
                # Archive (delete) message from queue
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT pgmq.archive(queue_name => %s, msg_id => %s)",
                        ("marketplace_cleanup_queue", msg_id),
                    )
                    conn.commit()

                logger.info(
                    f"  Cleanup task completed and archived (msg_id: {msg_id})"
                )
            else:
                # Let message become visible again for retry
                # PGMQ will automatically retry based on visibility timeout
                logger.warning(
                    f"⚠️  Cleanup task failed, will retry (msg_id: {msg_id})"
                )

        except Exception as e:
            logger.error(f"Worker error: {e}", exc_info=True)
            # Close connection on error to force reconnect
            if conn:
                try:
                    conn.close()
                except:
                    pass
                conn = None
            await asyncio.sleep(10)  # Back off on error


async def verify_websocket_auth(websocket: WebSocket) -> tuple[bool, str]:
    """
    Verify WebSocket authentication before accepting connection.

    Returns:
        tuple: (is_valid, user_id or error_message)
    """
    # Get token from query parameters
    token = websocket.query_params.get("token")

    if not token:
        logger.warning("WebSocket connection attempt without token")
        return False, "Missing authentication token"

    try:
        # Verify JWT token
        user_id = extract_user_id_from_token(token)
        if not user_id:
            logger.warning("WebSocket connection attempt with invalid token")
            return False, "Invalid authentication token"

        logger.info(f"  WebSocket authenticated for user: {user_id}")
        return True, user_id

    except Exception as e:
        logger.error(f"WebSocket auth error: {e}")
        return False, "Authentication failed"


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    Production WebSocket endpoint using HybridAgent.
    
    Combines:
    - SDK-style orchestration for smart tool planning
    - Token-level streaming for smooth UI experience
    - MCP server support for external integrations
    
    Protocol:
    1. Client connects with ?token=JWT&org_id=...&project_id=...
    2. Server authenticates, loads MCP servers, creates HybridAgent
    3. Client sends: {"prompt": "...", "session_id": "...", "conversation_id": "..."}
    4. Server streams: {"type": "delta", "content": "token"}
    5. Server sends tool events during processing
    6. Server sends: {"type": "complete"} when done
    """
    audit = get_audit_service()
    client_ip = websocket.client.host if websocket.client else None

    # Extract params from query
    ws_org_id = websocket.query_params.get("org_id") or None
    ws_project_id = websocket.query_params.get("project_id") or None
    token = websocket.query_params.get("token") or ""
    logger.info(f"WebSocket params - org_id: {ws_org_id}, project_id: {ws_project_id}")

    # Authenticate BEFORE accepting connection (prevents DoS)
    is_valid, result = await verify_websocket_auth(websocket)
    if not is_valid:
        logger.warning(f"🚫 WebSocket auth failed: {result}")
        await audit.log_auth_failed(
            user_id=None,
            error_code="INVALID_TOKEN",
            error_message=result,
            source_ip=client_ip,
            org_id=ws_org_id
        )
        await websocket.close(code=4001, reason="Unauthorized")
        return

    # Accept connection - user is authenticated
    await websocket.accept()
    user_id = result
    session_id = str(uuid.uuid4())
    logger.info(f"WebSocket accepted for user: {user_id}")

    # Initialize MCP tool manager
    mcp_manager = None
    mcp_tools = []
    
    try:
        # Load user's MCP servers
        logger.info(f"Loading MCP servers for user: {user_id}")
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
    
    # Create HybridAgent config
    config = HybridAgentConfig(
        model="claude-sonnet-4-20250514",
        streaming_model="claude-sonnet-4-20250514",
        planning_model="claude-sonnet-4-20250514",
        max_tokens=4096,
        max_planning_tokens=1024,
        tools=all_tools,
        system_prompt="""You are an AI assistant specialized in incident response and DevOps.
You help users manage incidents, analyze alerts, and troubleshoot issues.

## Tool Selection Guidelines

**For InRes Incident Operations (ALWAYS use built-in tools):**
- Use `get_incidents` to list incidents from InRes
- Use `get_incident_details` to fetch a specific incident
- Use `acknowledge_incident` to acknowledge an incident
- Use `resolve_incident` to resolve an incident
- Use `get_incident_stats` for statistics

**For External Integrations (MCP tools prefixed with mcp__):**
- Use Coralogix MCP tools for querying logs
- Use Confluence MCP tools for documentation
- Use other MCP tools for their respective services

Be concise but thorough in your responses."""
    )
    
    # Create HybridAgent
    agent = HybridAgent(config=config)
    
    # Create tool context and executor
    tool_context = ToolContext(org_id=ws_org_id, project_id=ws_project_id)
    tool_executor = create_tool_executor(
        auth_token=token,
        context=tool_context,
        mcp_manager=mcp_manager,
        user_id=user_id,
        session_id=session_id
    )
    
    # Log session created
    await audit.log_session_created(
        user_id=user_id,
        session_id=session_id,
        source_ip=client_ip,
        user_agent=websocket.headers.get("user-agent"),
        org_id=ws_org_id,
        project_id=ws_project_id
    )

    # Send session info to client
    await websocket.send_json({
        "type": "session_created",
        "session_id": session_id,
        "conversation_id": session_id,
        "agent_type": "hybrid",
        "message": "Hybrid agent session established",
        "mcp_servers": mcp_manager.server_count if mcp_manager else 0,
        "total_tools": len(all_tools)
    })
    logger.info(f"📤 Sent session_created: {session_id}")

    # Output queue for streaming events
    output_queue: asyncio.Queue = asyncio.Queue()
    
    # Track session state
    is_first_message = True
    conversation_id = session_id
    stream_task = None
    sender_task = None
    heartbeat_task_ref = None

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

    async def heartbeat():
        """Send periodic pings."""
        try:
            while True:
                await asyncio.sleep(30)
                await output_queue.put({"type": "ping", "timestamp": time.time()})
        except asyncio.CancelledError:
            pass

    try:
        sender_task = asyncio.create_task(send_events())
        heartbeat_task_ref = asyncio.create_task(heartbeat())
        
        while True:
            try:
                raw_message = await websocket.receive_text()
                message = json.loads(raw_message)
                
                msg_type = message.get("type", "chat")
                
                # Handle pong
                if msg_type == "pong":
                    continue
                
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
                
                # Update conversation_id if provided (for resume)
                if message.get("conversation_id"):
                    conversation_id = message.get("conversation_id")
                
                logger.info(f"Processing: {prompt[:50]}...")
                
                # Audit: log chat message
                await audit.log_chat_message(
                    user_id=user_id,
                    session_id=session_id,
                    conversation_id=conversation_id,
                    message_preview=prompt[:100],
                    org_id=tool_context.org_id,
                    project_id=tool_context.project_id
                )
                
                # Save conversation on first message
                if is_first_message:
                    await save_conversation(
                        user_id=user_id,
                        conversation_id=conversation_id,
                        first_message=prompt,
                        model="claude-sonnet-4-hybrid",
                        metadata={
                            "org_id": tool_context.org_id,
                            "project_id": tool_context.project_id,
                            "mode": "hybrid"
                        }
                    )
                    is_first_message = False
                
                # Save user message
                await save_message(
                    conversation_id=conversation_id,
                    role="user",
                    content=prompt
                )
                
                # Cancel existing stream
                if stream_task and not stream_task.done():
                    stream_task.cancel()
                    try:
                        await stream_task
                    except asyncio.CancelledError:
                        pass
                
                # Process with hybrid agent
                async def process_and_save():
                    """Process with HybridAgent and save response."""
                    response = await agent.process_message(
                        prompt=prompt,
                        output_queue=output_queue,
                        tool_executor=tool_executor
                    )
                    
                    if response:
                        await save_message(
                            conversation_id=conversation_id,
                            role="assistant",
                            content=response
                        )
                        await update_conversation_activity(conversation_id)
                    
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
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "error": sanitize_error_message(e, "in WebSocket")
            })
        except Exception:
            pass
    finally:
        # Cleanup
        logger.info(f"Cleaning up session: {session_id}")
        
        if stream_task and not stream_task.done():
            stream_task.cancel()
        if heartbeat_task_ref and not heartbeat_task_ref.done():
            heartbeat_task_ref.cancel()
        if sender_task and not sender_task.done():
            await output_queue.put(None)
            sender_task.cancel()
        
        # Release MCP servers
        try:
            pool = await get_mcp_pool()
            await pool.release_servers_for_user(user_id)
        except Exception as e:
            logger.error(f"Failed to release MCP servers: {e}")
        
        logger.info(f"Session cleanup complete: {session_id}")


@app.websocket("/ws/secure/chat")
async def websocket_secure_chat(websocket: WebSocket):
    """
    Zero-Trust Secure WebSocket for AI Agent using HybridAgent.

    Every message is cryptographically signed by the device and verified.
    This prevents session hijacking and replay attacks.

    Authentication flow:
    1. Client sends signed auth message with device certificate
    2. Server verifies certificate was signed by trusted instance
    3. Every subsequent message is signed by device's private key
    4. Server verifies each message against device's public key
    """
    await websocket.accept()

    audit = get_audit_service()
    client_ip = websocket.client.host if websocket.client else None
    verifier = get_verifier()

    # Extract org_id and project_id from query params
    ws_org_id = websocket.query_params.get("org_id") or None
    ws_project_id = websocket.query_params.get("project_id") or None
    logger.info(f"Secure WebSocket params - org_id: {ws_org_id}, project_id: {ws_project_id}")
    
    session = None
    session_id = None
    user_id = None
    
    # Agent and task references
    agent = None
    mcp_manager = None
    stream_task = None
    sender_task = None
    heartbeat_task_ref = None
    output_queue = asyncio.Queue()

    try:
        # Wait for authentication message
        logger.info("Waiting for Zero-Trust authentication...")
        auth_data = await asyncio.wait_for(
            websocket.receive_json(),
            timeout=30.0
        )

        if auth_data.get("type") != "authenticate":
            await audit.log_auth_failed(
                user_id=None,
                error_code="INVALID_AUTH_TYPE",
                error_message="Expected authentication message",
                source_ip=client_ip
            )
            await websocket.send_json({
                "type": "auth_error",
                "error": "Expected authentication message"
            })
            await websocket.close(code=4001)
            return

        # Verify device certificate
        cert_dict = auth_data.get("certificate")
        existing_session_id = auth_data.get("session_id")

        if not cert_dict:
            await audit.log_auth_failed(
                user_id=None,
                error_code="MISSING_CERTIFICATE",
                error_message="Missing device certificate",
                source_ip=client_ip
            )
            await websocket.send_json({
                "type": "auth_error",
                "error": "Missing device certificate"
            })
            await websocket.close(code=4002)
            return

        # Authenticate with verifier
        session, error = await verifier.authenticate(cert_dict, existing_session_id)

        if not session:
            logger.warning(f"🚫 Zero-Trust authentication failed: {error}")
            error_code = "AUTH_FAILED"
            if "expired" in error.lower():
                error_code = "CERTIFICATE_EXPIRED"
            elif "invalid" in error.lower():
                error_code = "INVALID_CERTIFICATE"
            await audit.log_auth_failed(
                user_id=cert_dict.get("user_id"),
                error_code=error_code,
                error_message=error,
                source_ip=client_ip,
                metadata={"instance_id": cert_dict.get("instance_id")}
            )
            await websocket.send_json({
                "type": "auth_error",
                "error": error
            })
            await websocket.close(code=4003)
            return

        session_id = session.session_id
        user_id = session.user_id
        logger.info(f"Zero-Trust authenticated: user={user_id}, session={session_id}")

        # Log successful authentication
        await audit.log_session_authenticated(
            user_id=user_id,
            session_id=session_id,
            device_cert_id=cert_dict.get("id", ""),
            instance_id=cert_dict.get("instance_id", ""),
            source_ip=client_ip,
            org_id=ws_org_id,
            project_id=ws_project_id,
            metadata={"permissions": session.permissions}
        )

        # Initialize MCP tool manager
        mcp_tools = []
        try:
            logger.info(f"Loading MCP servers for user: {user_id}")
            user_mcp_config = await get_user_mcp_servers(auth_token="", user_id=user_id)
            
            if user_mcp_config:
                logger.info(f"Found {len(user_mcp_config)} MCP server configs")
                pool = await get_mcp_pool()
                mcp_manager = await pool.get_servers_for_user(user_id, user_mcp_config)
                mcp_tools = mcp_manager.get_all_tools()
                logger.info(f"Loaded {len(mcp_tools)} MCP tools")
            else:
                mcp_manager = MCPToolManager()
        except Exception as e:
            logger.error(f"Failed to load MCP servers: {e}")
            mcp_manager = MCPToolManager()

        # Combine tools
        all_tools = INCIDENT_TOOLS.copy()
        all_tools.extend(mcp_tools)

        # Create HybridAgent
        config = HybridAgentConfig(
            model="claude-sonnet-4-20250514",
            streaming_model="claude-sonnet-4-20250514",
            planning_model="claude-sonnet-4-20250514",
            max_tokens=4096,
            max_planning_tokens=1024,
            tools=all_tools,
            system_prompt="""You are an AI assistant specialized in incident response and DevOps.
You help users manage incidents, analyze alerts, and troubleshoot issues.
Be concise but thorough in your responses."""
        )
        agent = HybridAgent(config=config)

        # Create tool executor
        tool_context = ToolContext(org_id=ws_org_id, project_id=ws_project_id)
        tool_executor = create_tool_executor(
            auth_token="",  # Zero-Trust uses device cert
            context=tool_context,
            mcp_manager=mcp_manager,
            user_id=user_id,
            session_id=session_id
        )

        # Send auth success with session info
        await websocket.send_json({
            "type": "authenticated",
            "session_id": session_id,
            "conversation_id": session_id,
            "user_id": user_id,
            "permissions": session.permissions,
            "agent_type": "hybrid",
            "mcp_servers": mcp_manager.server_count if mcp_manager else 0,
            "total_tools": len(all_tools)
        })

        # Track session state
        is_first_message = True
        conversation_id = session_id

        async def send_events():
            """Send events from queue to WebSocket."""
            try:
                while True:
                    event = await output_queue.get()
                    if event is None:
                        break
                    await websocket.send_json(event)
            except WebSocketDisconnect:
                pass
            except Exception as e:
                logger.error(f"Send error: {e}")

        async def heartbeat():
            """Send periodic pings."""
            try:
                while True:
                    await asyncio.sleep(30)
                    await output_queue.put({"type": "ping", "timestamp": time.time()})
            except asyncio.CancelledError:
                pass

        sender_task = asyncio.create_task(send_events())
        heartbeat_task_ref = asyncio.create_task(heartbeat())

        while True:
            try:
                signed_message = await websocket.receive_json()

                # Handle pong (not signed)
                if signed_message.get("type") == "pong":
                    continue

                # Verify signature on every message
                is_valid, error_msg, data = verifier.verify_message(
                    signed_message, session_id
                )

                if not is_valid:
                    logger.warning(f"🚫 Message verification failed: {error_msg}")
                    error_type = EventType.SIGNATURE_INVALID
                    if "nonce" in error_msg.lower() or "replay" in error_msg.lower():
                        error_type = EventType.NONCE_REPLAY
                    await audit.log_security_event(
                        event_type=error_type,
                        user_id=user_id,
                        action="verify_message",
                        error_code="VERIFICATION_FAILED",
                        error_message=error_msg,
                        source_ip=client_ip,
                        session_id=session_id
                    )
                    await websocket.send_json({
                        "type": "error",
                        "error": f"Message verification failed: {error_msg}"
                    })
                    continue

                msg_type = signed_message.get("payload", {}).get("type", "")

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
                if msg_type == "chat_message":
                    prompt = data.get("prompt", "")
                    if not prompt:
                        await websocket.send_json({
                            "type": "error",
                            "error": "Empty prompt"
                        })
                        continue

                    # Update context if provided
                    msg_org_id = data.get("org_id")
                    msg_project_id = data.get("project_id")
                    if msg_org_id or msg_project_id:
                        tool_context.update(org_id=msg_org_id, project_id=msg_project_id)

                    if data.get("conversation_id"):
                        conversation_id = data.get("conversation_id")

                    logger.info(f"Processing: {prompt[:50]}...")

                    # Audit
                    await audit.log_chat_message(
                        user_id=user_id,
                        session_id=session_id,
                        conversation_id=conversation_id,
                        message_preview=prompt[:100],
                        org_id=tool_context.org_id,
                        project_id=tool_context.project_id
                    )

                    # Save conversation on first message
                    if is_first_message:
                        await save_conversation(
                            user_id=user_id,
                            conversation_id=conversation_id,
                            first_message=prompt,
                            model="claude-sonnet-4-hybrid",
                            metadata={
                                "org_id": tool_context.org_id,
                                "project_id": tool_context.project_id,
                                "mode": "hybrid-secure"
                            }
                        )
                        is_first_message = False

                    await save_message(
                        conversation_id=conversation_id,
                        role="user",
                        content=prompt
                    )

                    # Cancel existing stream
                    if stream_task and not stream_task.done():
                        stream_task.cancel()
                        try:
                            await stream_task
                        except asyncio.CancelledError:
                            pass

                    # Process with hybrid agent
                    async def process_and_save():
                        response = await agent.process_message(
                            prompt=prompt,
                            output_queue=output_queue,
                            tool_executor=tool_executor
                        )
                        if response:
                            await save_message(
                                conversation_id=conversation_id,
                                role="assistant",
                                content=response
                            )
                            await update_conversation_activity(conversation_id)
                        return response

                    stream_task = asyncio.create_task(process_and_save())

            except WebSocketDisconnect:
                logger.info(f"Secure WebSocket disconnected: {session_id}")
                break

    except asyncio.TimeoutError:
        logger.warning("⏰ Zero-Trust authentication timeout")
        try:
            await websocket.send_json({
                "type": "auth_error",
                "error": "Authentication timeout"
            })
        except:
            pass
    except WebSocketDisconnect:
        logger.info("🔌 Secure WebSocket disconnected")
    except Exception as e:
        logger.error(f"Secure WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "error": sanitize_error_message(e, "in secure WebSocket")
            })
        except:
            pass
    finally:
        if session_id:
            logger.info(f"Session {session_id} kept for potential reconnection")

        # Cleanup
        if stream_task and not stream_task.done():
            stream_task.cancel()
        if heartbeat_task_ref and not heartbeat_task_ref.done():
            heartbeat_task_ref.cancel()
        if sender_task and not sender_task.done():
            await output_queue.put(None)
            sender_task.cancel()

        # Release MCP servers
        if user_id:
            try:
                pool = await get_mcp_pool()
                await pool.release_servers_for_user(user_id)
            except Exception as e:
                logger.error(f"Failed to release MCP servers: {e}")

        logger.info("🧹 Secure WebSocket cleanup complete")


if __name__ == "__main__":
    import os

    import uvicorn

    # Initialize Zero-Trust verifier with backend URL
    backend_url = os.getenv("inres_BACKEND_URL", "")
    if backend_url:
        init_verifier(backend_url)
        logger.info(f"  Zero-Trust verifier initialized with backend: {backend_url}")
    else:
        logger.warning("inres_BACKEND_URL not set, Zero-Trust features limited")

    # Disable auto-reload in production to prevent sync issues
    # Auto-reload can cause server restarts during file operations (like sync)
    # which leads to background tasks hanging
    reload_enabled = os.getenv("DEV_MODE", "false").lower() == "true"

    uvicorn.run(
        "claude_agent_api_v1:app", host="0.0.0.0", port=8002, reload=reload_enabled
    )
