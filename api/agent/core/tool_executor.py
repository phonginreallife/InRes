"""
Unified Tool Executor.

Provides a single interface for executing tools regardless of type:
- Built-in tools (InRes incident management): HTTP calls to backend API
- MCP tools: Routed to MCP servers via subprocess/pool

Both legacy and streaming modes use this unified executor.
"""

import json
import logging
import os
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Result from tool execution."""
    content: str
    is_error: bool = False
    tool_use_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "content": self.content,
            "is_error": self.is_error,
            "tool_use_id": self.tool_use_id
        }


class ToolContext:
    """
    Mutable context for tool execution.
    
    Holds organization and project context that can be updated
    per-message to support multi-tenant tool execution.
    """
    
    def __init__(self, org_id: str = None, project_id: str = None):
        self.org_id = org_id
        self.project_id = project_id
    
    def update(self, org_id: str = None, project_id: str = None) -> None:
        """Update context with new values (only if provided)."""
        if org_id:
            self.org_id = org_id
        if project_id:
            self.project_id = project_id


class ToolExecutor:
    """
    Unified tool executor for both built-in and MCP tools.
    
    Usage:
        executor = ToolExecutor(auth_token="...", context=ToolContext(...))
        result = await executor.execute("get_incidents", {"limit": 10})
    """
    
    def __init__(
        self,
        auth_token: str,
        context: ToolContext = None,
        mcp_manager: Any = None,  # MCPToolManager
        api_base: str = None,
        audit_service: Any = None,
        user_id: str = None,
        session_id: str = None,
    ):
        """
        Initialize the tool executor.
        
        Args:
            auth_token: JWT token for API authentication
            context: Tool context with org/project IDs
            mcp_manager: MCP tool manager for external integrations
            api_base: Base URL for InRes API (default from env)
            audit_service: Audit service for logging tool executions
            user_id: User ID for audit logging
            session_id: Session ID for audit logging
        """
        self.auth_token = auth_token
        self.context = context or ToolContext()
        self.mcp_manager = mcp_manager
        self.api_base = api_base or os.getenv("INRES_API_URL", "http://inres-api:8080")
        self.audit = audit_service
        self.user_id = user_id
        self.session_id = session_id
    
    async def execute(self, tool_name: str, tool_input: Dict[str, Any]) -> ToolResult:
        """
        Execute a tool and return the result.
        
        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool
        
        Returns:
            ToolResult with content and error status
        """
        request_id = str(uuid.uuid4())
        
        logger.info(
            f"Executing tool: {tool_name} "
            f"(org_id={self.context.org_id}, project_id={self.context.project_id})"
        )
        
        # Audit: log tool request
        if self.audit and self.user_id and self.session_id:
            try:
                await self.audit.log_tool_requested(
                    user_id=self.user_id,
                    session_id=self.session_id,
                    tool_name=tool_name,
                    tool_input=tool_input,
                    request_id=request_id
                )
            except Exception as e:
                logger.warning(f"Failed to audit tool request: {e}")
        
        try:
            # Route MCP tools to MCP manager
            if tool_name.startswith("mcp__") and self.mcp_manager:
                result = await self._execute_mcp_tool(tool_name, tool_input)
            else:
                result = await self._execute_builtin_tool(tool_name, tool_input)
            
            return result
            
        except Exception as e:
            logger.error(f"Tool execution error: {e}", exc_info=True)
            return ToolResult(
                content=json.dumps({"error": str(e)}),
                is_error=True
            )
    
    async def _execute_mcp_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any]
    ) -> ToolResult:
        """Execute an MCP tool via the MCP manager."""
        logger.info(f"Routing to MCP: {tool_name}")
        
        try:
            result = await self.mcp_manager.call_tool(tool_name, tool_input)
            return ToolResult(content=result)
        except Exception as e:
            logger.error(f"MCP tool error: {e}")
            return ToolResult(
                content=json.dumps({"error": f"MCP tool failed: {str(e)}"}),
                is_error=True
            )
    
    async def _execute_builtin_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any]
    ) -> ToolResult:
        """Execute a built-in tool via HTTP API."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}",
        }
        if self.context.org_id:
            headers["X-Org-ID"] = self.context.org_id
        if self.context.project_id:
            headers["X-Project-ID"] = self.context.project_id
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                result = await self._route_builtin_tool(client, headers, tool_name, tool_input)
                return result
        except httpx.TimeoutException:
            logger.error(f"Tool {tool_name} timed out")
            return ToolResult(
                content=json.dumps({"error": f"Tool {tool_name} timed out"}),
                is_error=True
            )
        except Exception as e:
            logger.error(f"Tool execution error: {e}", exc_info=True)
            return ToolResult(
                content=json.dumps({"error": str(e)}),
                is_error=True
            )
    
    async def _route_builtin_tool(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        tool_name: str,
        tool_input: Dict[str, Any]
    ) -> ToolResult:
        """Route to specific built-in tool implementation."""
        
        if tool_name == "get_incidents":
            return await self._tool_get_incidents(client, headers, tool_input)
        
        elif tool_name == "get_incident_details":
            return await self._tool_get_incident_details(client, headers, tool_input)
        
        elif tool_name == "get_incident_stats":
            return await self._tool_get_incident_stats(client, headers, tool_input)
        
        elif tool_name == "acknowledge_incident":
            return await self._tool_acknowledge_incident(client, headers, tool_input)
        
        elif tool_name == "resolve_incident":
            return await self._tool_resolve_incident(client, headers, tool_input)
        
        else:
            return ToolResult(
                content=json.dumps({"error": f"Unknown tool: {tool_name}"}),
                is_error=True
            )
    
    # =========================================================================
    # Built-in Tool Implementations
    # =========================================================================
    
    async def _tool_get_incidents(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        tool_input: Dict[str, Any]
    ) -> ToolResult:
        """Get list of incidents."""
        params = {"limit": tool_input.get("limit", 10)}
        if tool_input.get("status"):
            params["status"] = tool_input["status"]
        if tool_input.get("severity"):
            params["severity"] = tool_input["severity"]
        
        resp = await client.get(
            f"{self.api_base}/incidents",
            headers=headers,
            params=params
        )
        
        if resp.status_code == 200:
            return ToolResult(content=json.dumps(resp.json(), indent=2, default=str))
        
        return ToolResult(
            content=json.dumps({"error": f"API error: {resp.status_code}"}),
            is_error=True
        )
    
    async def _tool_get_incident_details(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        tool_input: Dict[str, Any]
    ) -> ToolResult:
        """Get details of a specific incident."""
        incident_id = tool_input.get("incident_id")
        
        if not incident_id:
            return ToolResult(
                content=json.dumps({"error": "incident_id is required"}),
                is_error=True
            )
        
        logger.info(f"Fetching incident {incident_id}")
        resp = await client.get(
            f"{self.api_base}/incidents/{incident_id}",
            headers=headers
        )
        
        if resp.status_code == 200:
            return ToolResult(content=json.dumps(resp.json(), indent=2, default=str))
        
        error_body = resp.text
        logger.error(f"Failed to fetch incident {incident_id}: {resp.status_code}")
        return ToolResult(
            content=json.dumps({
                "error": f"Incident not found: {incident_id}",
                "status_code": resp.status_code,
                "details": error_body[:500] if error_body else None
            }),
            is_error=True
        )
    
    async def _tool_get_incident_stats(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        tool_input: Dict[str, Any]
    ) -> ToolResult:
        """Get incident statistics."""
        time_range = tool_input.get("time_range", "24h")
        
        resp = await client.get(
            f"{self.api_base}/incidents/stats",
            headers=headers,
            params={"range": time_range}
        )
        
        if resp.status_code == 200:
            return ToolResult(content=json.dumps(resp.json(), indent=2, default=str))
        
        # Fallback: calculate from incidents list
        resp = await client.get(
            f"{self.api_base}/incidents",
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
                
                return ToolResult(content=json.dumps({
                    "time_range": time_range,
                    "total_incidents": len(incidents),
                    "by_status": by_status,
                    "by_severity": by_severity,
                }, indent=2))
        
        return ToolResult(
            content=json.dumps({"error": "Could not fetch incident stats"}),
            is_error=True
        )
    
    async def _tool_acknowledge_incident(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        tool_input: Dict[str, Any]
    ) -> ToolResult:
        """Acknowledge an incident."""
        incident_id = tool_input.get("incident_id")
        
        if not incident_id:
            return ToolResult(
                content=json.dumps({"error": "incident_id is required"}),
                is_error=True
            )
        
        resp = await client.post(
            f"{self.api_base}/incidents/{incident_id}/acknowledge",
            headers=headers,
            json={"note": tool_input.get("note", "")}
        )
        
        if resp.status_code == 200:
            return ToolResult(content=json.dumps({
                "status": "success",
                "message": f"Incident {incident_id} acknowledged"
            }))
        
        return ToolResult(
            content=json.dumps({"error": f"Failed to acknowledge: {resp.status_code}"}),
            is_error=True
        )
    
    async def _tool_resolve_incident(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        tool_input: Dict[str, Any]
    ) -> ToolResult:
        """Resolve an incident."""
        incident_id = tool_input.get("incident_id")
        
        if not incident_id:
            return ToolResult(
                content=json.dumps({"error": "incident_id is required"}),
                is_error=True
            )
        
        resp = await client.post(
            f"{self.api_base}/incidents/{incident_id}/resolve",
            headers=headers,
            json={"resolution": tool_input.get("resolution", "")}
        )
        
        if resp.status_code == 200:
            return ToolResult(content=json.dumps({
                "status": "success",
                "message": f"Incident {incident_id} resolved"
            }))
        
        return ToolResult(
            content=json.dumps({"error": f"Failed to resolve: {resp.status_code}"}),
            is_error=True
        )


def create_tool_executor(
    auth_token: str,
    context: ToolContext = None,
    mcp_manager: Any = None,
    audit_service: Any = None,
    user_id: str = None,
    session_id: str = None,
) -> Callable[[str, Dict[str, Any]], str]:
    """
    Create a callable tool executor function.
    
    This returns a simple async function that can be passed to agents
    as the tool_executor parameter.
    
    Args:
        auth_token: JWT token for authentication
        context: Tool context with org/project IDs
        mcp_manager: MCP manager for external tools
        audit_service: Audit service for logging
        user_id: User ID for audit
        session_id: Session ID for audit
    
    Returns:
        Async function: (tool_name, tool_input) -> result_string
    """
    executor = ToolExecutor(
        auth_token=auth_token,
        context=context,
        mcp_manager=mcp_manager,
        audit_service=audit_service,
        user_id=user_id,
        session_id=session_id,
    )
    
    async def execute(tool_name: str, tool_input: Dict[str, Any]) -> str:
        result = await executor.execute(tool_name, tool_input)
        return result.content
    
    return execute
