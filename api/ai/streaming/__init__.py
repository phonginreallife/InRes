"""
Streaming Module - Token-level LLM Streaming.

This module provides true token-by-token streaming from the Anthropic API,
delivering a fast and responsive user experience.

Components:
- StreamingAgent: Agent implementation using direct Anthropic API
- routes: WebSocket endpoint for /ws/stream
- mcp_client: MCP server pool for external tool integrations

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

# Re-export from submodules for convenience
# These will be available after migration is complete

__all__ = [
    "StreamingAgent",
    "create_streaming_agent", 
    "INCIDENT_TOOLS",
    "MCPToolManager",
    "MCPServerPool",
    "get_mcp_pool",
]

# Lazy imports to avoid circular dependencies during migration
def __getattr__(name):
    if name in ("StreamingAgent", "create_streaming_agent", "INCIDENT_TOOLS"):
        from streaming_agent import StreamingAgent, create_streaming_agent, INCIDENT_TOOLS
        return locals()[name]
    
    if name in ("MCPToolManager", "MCPServerPool", "get_mcp_pool"):
        from mcp_streaming_client import MCPToolManager, MCPServerPool, get_mcp_pool
        return locals()[name]
    
    raise AttributeError(f"module 'streaming' has no attribute '{name}'")
