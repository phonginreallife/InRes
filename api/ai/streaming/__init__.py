"""
Streaming Module - Token-level LLM Streaming.

This module provides true token-by-token streaming from the Anthropic API,
delivering a fast and responsive user experience.

Components:
- agent.py: StreamingAgent implementation using direct Anthropic API
- routes.py: WebSocket endpoint for /ws/stream
- mcp_client.py: MCP server pool for external tool integrations

Features:
- True token streaming (not block streaming)
- MCP tool support via subprocess/connection pool
- Compatible with audit and conversation history modules
- Graceful interruption handling

Usage:
    from streaming import StreamingAgent, create_streaming_agent
    
    agent = create_streaming_agent(api_key="...", include_tools=True)
    response = await agent.stream_response(prompt, output_queue, tool_executor)
"""

from .agent import StreamingAgent, create_streaming_agent, INCIDENT_TOOLS
from .mcp_client import MCPToolManager, MCPServerPool, get_mcp_pool
from .routes import router as streaming_router
from .mcp_config import MCPConfigManager

__all__ = [
    # Agent
    "StreamingAgent",
    "create_streaming_agent", 
    "INCIDENT_TOOLS",
    # MCP
    "MCPToolManager",
    "MCPServerPool",
    "get_mcp_pool",
    "MCPConfigManager",
    # Routes
    "streaming_router",
]
