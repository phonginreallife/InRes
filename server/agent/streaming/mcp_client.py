"""
Lightweight MCP Client for Streaming Endpoint.

This module provides a simple MCP client that can communicate with
stdio-based MCP servers to get tool definitions and execute tool calls.

MCP Protocol (JSON-RPC over stdio):
1. initialize - handshake with server
2. tools/list - get available tools
3. tools/call - execute a tool

SCALABILITY FEATURES:
- Global connection pool for shared MCP servers
- Reference counting for cleanup
- Lazy initialization (start on first tool call)
- Configurable max servers per user
- Automatic cleanup of idle servers
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Set
from weakref import WeakSet

logger = logging.getLogger(__name__)

# Configuration for scalability
MAX_MCP_SERVERS_PER_USER = int(os.getenv("MAX_MCP_SERVERS_PER_USER", "5"))
MAX_GLOBAL_MCP_SERVERS = int(os.getenv("MAX_GLOBAL_MCP_SERVERS", "50"))
MCP_SERVER_IDLE_TIMEOUT = int(os.getenv("MCP_SERVER_IDLE_TIMEOUT", "300"))  # 5 minutes


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
    
    def get_server_configs(self) -> Dict[str, Any]:
        """
        Get server configurations for SDK orchestrator.
        
        Returns dict that can be passed to SDKOrchestrator.mcp_servers.
        Note: The SDK orchestrator will need to handle MCP integration
        differently than direct API usage.
        
        Returns:
            Dict of server configs: {name: {command, args, env}}
        """
        configs = {}
        for name, server in self.servers.items():
            configs[name] = {
                "command": server.command,
                "args": server.args,
                "env": server.env or {},
                "tools": server.tools,  # Include discovered tools
            }
        return configs


# =============================================================================
# GLOBAL MCP SERVER POOL (for scalability)
# =============================================================================

class MCPServerPool:
    """
    Global pool of MCP servers shared across sessions.
    
    Scalability features:
    - Connection pooling: Same MCP server config shares one process
    - Reference counting: Clean up when no sessions use a server
    - Idle timeout: Auto-cleanup of unused servers
    - Limits: Max servers per user and globally
    
    Usage:
        pool = get_mcp_pool()
        servers = await pool.get_servers_for_user(user_id, config)
        # ... use servers ...
        await pool.release_servers_for_user(user_id)
    """
    
    _instance: Optional['MCPServerPool'] = None
    _lock = asyncio.Lock()
    
    def __init__(self):
        # server_key -> MCPServerClient
        self._servers: Dict[str, MCPServerClient] = {}
        # server_key -> set of user_ids using it
        self._server_refs: Dict[str, Set[str]] = {}
        # server_key -> last access time
        self._last_access: Dict[str, float] = {}
        # user_id -> set of server_keys
        self._user_servers: Dict[str, Set[str]] = {}
        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
    
    @classmethod
    async def get_instance(cls) -> 'MCPServerPool':
        """Get or create the singleton pool instance."""
        async with cls._lock:
            if cls._instance is None:
                cls._instance = MCPServerPool()
                await cls._instance._start_cleanup_task()
            return cls._instance
    
    async def _start_cleanup_task(self):
        """Start background cleanup of idle servers."""
        if self._running:
            return
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def _cleanup_loop(self):
        """Periodically clean up idle servers."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._cleanup_idle_servers()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Pool cleanup error: {e}")
    
    async def _cleanup_idle_servers(self):
        """Stop servers that have been idle too long."""
        now = time.time()
        to_remove = []
        
        for key, last_access in self._last_access.items():
            if now - last_access > MCP_SERVER_IDLE_TIMEOUT:
                refs = self._server_refs.get(key, set())
                if not refs:  # No active users
                    to_remove.append(key)
        
        for key in to_remove:
            await self._stop_server(key)
            logger.info(f"Cleaned up idle MCP server: {key}")
    
    def _make_server_key(self, config: Dict[str, Any]) -> str:
        """Create unique key for a server config."""
        # Key based on command + args + env (sorted for consistency)
        parts = [
            config.get("command", ""),
            json.dumps(config.get("args", []), sort_keys=True),
            json.dumps(config.get("env", {}), sort_keys=True)
        ]
        return ":".join(parts)
    
    async def get_servers_for_user(
        self,
        user_id: str,
        config: Dict[str, Any]
    ) -> MCPToolManager:
        """
        Get MCP servers for a user, using pooled connections where possible.
        
        Args:
            user_id: User identifier
            config: Dict of server_name -> server_config
        
        Returns:
            MCPToolManager with user's servers
        """
        manager = MCPToolManager()
        user_server_keys: Set[str] = set()
        
        servers_started = 0
        
        for name, server_config in config.items():
            # Skip non-stdio servers
            if "command" not in server_config:
                continue
            
            # Check user limit
            if servers_started >= MAX_MCP_SERVERS_PER_USER:
                logger.warning(f"User {user_id} hit MCP server limit ({MAX_MCP_SERVERS_PER_USER})")
                break
            
            # Check global limit
            if len(self._servers) >= MAX_GLOBAL_MCP_SERVERS:
                logger.warning(f"Global MCP server limit reached ({MAX_GLOBAL_MCP_SERVERS})")
                break
            
            server_key = self._make_server_key(server_config)
            
            # Try to reuse existing server
            if server_key in self._servers:
                server = self._servers[server_key]
                if server._initialized:
                    # Add reference
                    self._server_refs.setdefault(server_key, set()).add(user_id)
                    self._last_access[server_key] = time.time()
                    user_server_keys.add(server_key)
                    manager.servers[name] = server
                    servers_started += 1
                    logger.debug(f"Reusing pooled MCP server: {name}")
                    continue
            
            # Start new server
            client = MCPServerClient(
                name=name,
                command=server_config["command"],
                args=server_config.get("args", []),
                env=server_config.get("env", {})
            )
            
            success = await client.start()
            if success:
                self._servers[server_key] = client
                self._server_refs.setdefault(server_key, set()).add(user_id)
                self._last_access[server_key] = time.time()
                user_server_keys.add(server_key)
                manager.servers[name] = client
                servers_started += 1
                logger.info(f"Started pooled MCP server: {name}")
        
        # Track user's servers
        self._user_servers[user_id] = user_server_keys
        
        return manager
    
    async def release_servers_for_user(self, user_id: str):
        """Release user's references to pooled servers."""
        server_keys = self._user_servers.pop(user_id, set())
        
        for key in server_keys:
            refs = self._server_refs.get(key, set())
            refs.discard(user_id)
            
            # If no more references and server idle, mark for cleanup
            if not refs:
                self._last_access[key] = time.time()
        
        logger.debug(f"Released {len(server_keys)} server refs for user {user_id}")
    
    async def _stop_server(self, key: str):
        """Stop and remove a server from the pool."""
        server = self._servers.pop(key, None)
        if server:
            await server.stop()
        self._server_refs.pop(key, None)
        self._last_access.pop(key, None)
    
    async def shutdown(self):
        """Shutdown the entire pool."""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        for key in list(self._servers.keys()):
            await self._stop_server(key)
        
        self._user_servers.clear()
        logger.info("MCP server pool shutdown complete")
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        return {
            "total_servers": len(self._servers),
            "total_users": len(self._user_servers),
            "max_per_user": MAX_MCP_SERVERS_PER_USER,
            "max_global": MAX_GLOBAL_MCP_SERVERS,
            "idle_timeout_seconds": MCP_SERVER_IDLE_TIMEOUT
        }


# Singleton accessor
_pool_instance: Optional[MCPServerPool] = None

async def get_mcp_pool() -> MCPServerPool:
    """Get the global MCP server pool."""
    global _pool_instance
    if _pool_instance is None:
        _pool_instance = await MCPServerPool.get_instance()
    return _pool_instance
