"""
Lightweight MCP Client for Streaming Endpoint.

This module provides a simple MCP client that can communicate with
stdio-based MCP servers to get tool definitions and execute tool calls.

MCP Protocol (JSON-RPC over stdio):
1. initialize - handshake with server
2. tools/list - get available tools
3. tools/call - execute a tool
"""

import asyncio
import json
import logging
import os
import subprocess
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MCPServerClient:
    """
    Client for a single MCP server (stdio-based).
    
    Manages the subprocess lifecycle and JSON-RPC communication.
    """
    
    def __init__(
        self,
        name: str,
        command: str,
        args: List[str] = None,
        env: Dict[str, str] = None
    ):
        self.name = name
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.process: Optional[asyncio.subprocess.Process] = None
        self.tools: List[Dict[str, Any]] = []
        self._request_id = 0
        self._initialized = False
        self._lock = asyncio.Lock()
    
    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id
    
    async def start(self) -> bool:
        """Start the MCP server subprocess."""
        try:
            # Prepare environment
            full_env = os.environ.copy()
            full_env.update(self.env)
            
            # Build command
            cmd = [self.command] + self.args
            logger.info(f"Starting MCP server '{self.name}': {' '.join(cmd)}")
            
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=full_env
            )
            
            # Initialize the server
            success = await self._initialize()
            if success:
                # Get available tools
                await self._list_tools()
                self._initialized = True
                logger.info(f"MCP server '{self.name}' started with {len(self.tools)} tools")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to start MCP server '{self.name}': {e}")
            return False
    
    async def stop(self):
        """Stop the MCP server subprocess."""
        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
            except Exception as e:
                logger.error(f"Error stopping MCP server '{self.name}': {e}")
            finally:
                self.process = None
                self._initialized = False
    
    async def _send_request(self, method: str, params: Dict = None) -> Optional[Dict]:
        """Send a JSON-RPC request and wait for response."""
        if not self.process or not self.process.stdin or not self.process.stdout:
            logger.error(f"MCP server '{self.name}' not running")
            return None
        
        async with self._lock:
            request = {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": method,
            }
            if params:
                request["params"] = params
            
            try:
                # Send request
                request_bytes = json.dumps(request).encode() + b"\n"
                self.process.stdin.write(request_bytes)
                await self.process.stdin.drain()
                
                # Read response (with timeout)
                response_line = await asyncio.wait_for(
                    self.process.stdout.readline(),
                    timeout=30.0
                )
                
                if not response_line:
                    logger.error(f"Empty response from MCP server '{self.name}'")
                    return None
                
                response = json.loads(response_line.decode())
                
                if "error" in response:
                    logger.error(f"MCP error from '{self.name}': {response['error']}")
                    return None
                
                return response.get("result")
                
            except asyncio.TimeoutError:
                logger.error(f"Timeout waiting for MCP server '{self.name}'")
                return None
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from MCP server '{self.name}': {e}")
                return None
            except Exception as e:
                logger.error(f"Error communicating with MCP server '{self.name}': {e}")
                return None
    
    async def _initialize(self) -> bool:
        """Send initialize request to MCP server."""
        result = await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "inres-streaming",
                "version": "1.0.0"
            }
        })
        
        if result:
            logger.debug(f"MCP server '{self.name}' initialized: {result.get('serverInfo', {})}")
            
            # Send initialized notification
            await self._send_notification("notifications/initialized", {})
            return True
        
        return False
    
    async def _send_notification(self, method: str, params: Dict = None):
        """Send a JSON-RPC notification (no response expected)."""
        if not self.process or not self.process.stdin:
            return
        
        notification = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params:
            notification["params"] = params
        
        try:
            notification_bytes = json.dumps(notification).encode() + b"\n"
            self.process.stdin.write(notification_bytes)
            await self.process.stdin.drain()
        except Exception as e:
            logger.error(f"Error sending notification to '{self.name}': {e}")
    
    async def _list_tools(self):
        """Get list of available tools from MCP server."""
        result = await self._send_request("tools/list", {})
        
        if result and "tools" in result:
            self.tools = result["tools"]
            logger.debug(f"MCP server '{self.name}' tools: {[t.get('name') for t in self.tools]}")
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Execute a tool and return the result."""
        if not self._initialized:
            return json.dumps({"error": f"MCP server '{self.name}' not initialized"})
        
        result = await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        
        if result is None:
            return json.dumps({"error": f"Tool call failed: {tool_name}"})
        
        # Extract content from result
        if isinstance(result, dict) and "content" in result:
            contents = result["content"]
            # Combine text content
            text_parts = []
            for item in contents:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
            return "\n".join(text_parts) if text_parts else json.dumps(result)
        
        return json.dumps(result) if result else "Tool executed successfully"
    
    def get_anthropic_tools(self) -> List[Dict[str, Any]]:
        """Convert MCP tools to Anthropic API format."""
        anthropic_tools = []
        
        for tool in self.tools:
            # MCP tool format -> Anthropic tool format
            anthropic_tool = {
                "name": f"mcp__{self.name}__{tool['name']}",  # Prefix with server name
                "description": tool.get("description", f"Tool from {self.name}"),
                "input_schema": tool.get("inputSchema", {"type": "object", "properties": {}})
            }
            anthropic_tools.append(anthropic_tool)
        
        return anthropic_tools


class MCPToolManager:
    """
    Manages multiple MCP servers and routes tool calls.
    
    Usage:
        manager = MCPToolManager()
        await manager.add_server("context7", "npx", ["-y", "@uptudev/mcp-context7"])
        tools = manager.get_all_tools()
        result = await manager.call_tool("mcp__context7__search", {...})
        await manager.shutdown()
    """
    
    def __init__(self):
        self.servers: Dict[str, MCPServerClient] = {}
    
    async def add_server(
        self,
        name: str,
        command: str,
        args: List[str] = None,
        env: Dict[str, str] = None
    ) -> bool:
        """Add and start an MCP server."""
        if name in self.servers:
            logger.warning(f"MCP server '{name}' already exists")
            return True
        
        client = MCPServerClient(name, command, args, env)
        success = await client.start()
        
        if success:
            self.servers[name] = client
            return True
        
        return False
    
    async def add_servers_from_config(self, config: Dict[str, Any]) -> int:
        """
        Add multiple servers from config dict.
        
        Config format (same as user_mcp_servers):
            {
                "context7": {
                    "command": "npx",
                    "args": ["-y", "@uptudev/mcp-context7"],
                    "env": {}
                }
            }
        
        Returns number of successfully started servers.
        """
        started = 0
        
        for name, server_config in config.items():
            # Only handle stdio servers (have "command")
            if "command" not in server_config:
                logger.debug(f"Skipping non-stdio MCP server: {name}")
                continue
            
            success = await self.add_server(
                name=name,
                command=server_config["command"],
                args=server_config.get("args", []),
                env=server_config.get("env", {})
            )
            
            if success:
                started += 1
        
        return started
    
    def get_all_tools(self) -> List[Dict[str, Any]]:
        """Get all tools from all servers in Anthropic format."""
        all_tools = []
        
        for server in self.servers.values():
            all_tools.extend(server.get_anthropic_tools())
        
        return all_tools
    
    def get_server_for_tool(self, tool_name: str) -> Optional[tuple[MCPServerClient, str]]:
        """
        Find the server for a tool and return (server, original_tool_name).
        
        Tool names are prefixed: mcp__{server_name}__{tool_name}
        """
        if not tool_name.startswith("mcp__"):
            return None
        
        parts = tool_name.split("__", 2)
        if len(parts) != 3:
            return None
        
        _, server_name, original_name = parts
        server = self.servers.get(server_name)
        
        if server:
            return (server, original_name)
        
        return None
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        Execute a tool by routing to the correct MCP server.
        
        Args:
            tool_name: Full tool name (e.g., "mcp__context7__search")
            arguments: Tool arguments
        
        Returns:
            Tool result as string
        """
        result = self.get_server_for_tool(tool_name)
        
        if not result:
            return json.dumps({"error": f"Unknown MCP tool: {tool_name}"})
        
        server, original_name = result
        return await server.call_tool(original_name, arguments)
    
    async def shutdown(self):
        """Stop all MCP servers."""
        for name, server in list(self.servers.items()):
            await server.stop()
            del self.servers[name]
        
        logger.info("All MCP servers stopped")
    
    @property
    def server_count(self) -> int:
        """Number of active servers."""
        return len(self.servers)
    
    @property
    def tool_count(self) -> int:
        """Total number of tools across all servers."""
        return sum(len(s.tools) for s in self.servers.values())
