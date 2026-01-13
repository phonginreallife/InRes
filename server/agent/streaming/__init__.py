"""
Streaming Module - Token-level LLM Streaming.

This module provides true token-by-token streaming from the Anthropic API,
delivering a fast and responsive user experience.

Components:
- agent.py: StreamingAgent and INCIDENT_TOOLS definitions
- mcp_client.py: MCP server pool for external tool integrations

Features:
- True token streaming (not block streaming)
- MCP tool support via subprocess/connection pool
- Compatible with audit and conversation history modules

Usage:
    from streaming import INCIDENT_TOOLS, MCPToolManager, get_mcp_pool
"""

from .agent import StreamingAgent, create_streaming_agent, INCIDENT_TOOLS
from .mcp_client import MCPToolManager, MCPServerPool, get_mcp_pool
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
]
