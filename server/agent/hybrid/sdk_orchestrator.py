"""
SDK Orchestrator - Planning Layer using Claude Agent SDK.

This module uses the Claude Agent SDK for:
1. Tool planning and execution with full SDK capabilities
2. MCP server integration for external tools
3. Permission handling

The orchestrator handles the "thinking" phase, while the streaming
layer (using direct Anthropic API) handles the "voice" phase.

Architecture:
    User Message
         │
         ▼
    ┌─────────────────────┐
    │  ClaudeSDKClient    │  ◄── Full SDK features
    │  (planning/tools)   │
    └─────────┬───────────┘
              │
              ▼
    Tool Results + Context
              │
              ▼
    ┌─────────────────────┐
    │  Direct Anthropic   │  ◄── Token streaming
    │  API (streaming)    │
    └─────────────────────┘
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    """Types of actions the orchestrator can decide on."""
    
    # Stream a text response to the user (use direct API)
    STREAM_RESPONSE = "stream_response"
    
    # Tools were executed, now stream response with results
    STREAM_AFTER_TOOLS = "stream_after_tools"
    
    # Error occurred during planning
    ERROR = "error"


@dataclass
class ToolExecution:
    """Record of a tool execution."""
    id: str
    name: str
    input: Dict[str, Any]
    result: str
    is_error: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "input": self.input,
            "result": self.result,
            "is_error": self.is_error
        }


@dataclass
class SDKOrchestratorResult:
    """
    Result from the SDK orchestrator.
    
    Contains all information needed for the streaming layer to continue.
    """
    action_type: ActionType
    
    # Tool executions that occurred
    tool_executions: List[ToolExecution] = field(default_factory=list)
    
    # Assistant's text response (may be partial if tools were used)
    text_response: str = ""
    
    # Thinking/reasoning content
    thinking: Optional[str] = None
    
    # Error message if action_type is ERROR
    error: Optional[str] = None
    
    # Updated message history after SDK processing
    messages: List[Dict[str, Any]] = field(default_factory=list)


class SDKOrchestrator:
    """
    Orchestrator that uses Claude Agent SDK for planning and tool execution.
    
    This class wraps the Claude Agent SDK to:
    1. Receive user prompts
    2. Let SDK decide if tools are needed
    3. Execute tools via SDK (with full MCP/permission support)
    4. Return results for the streaming layer
    
    The streaming layer then uses direct Anthropic API to stream
    the final response to the user.
    """
    
    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        system_prompt: str = None,
        mcp_servers: Dict[str, Any] = None,
        permission_mode: str = "default",  # acceptEdits, bypassPermissions, default, dontAsk, plan
        max_turns: int = 10,
    ):
        """
        Initialize the SDK orchestrator.
        
        Args:
            model: Model to use for SDK
            system_prompt: System prompt for the agent
            mcp_servers: MCP server configurations (including incident_tools)
            permission_mode: Permission mode for tool execution
            max_turns: Max turns for SDK conversation
        """
        self.model = model
        self.system_prompt = system_prompt or self._default_system_prompt()
        self.mcp_servers = mcp_servers or {}
        self.permission_mode = permission_mode
        self.max_turns = max_turns
        
        # Conversation state (maintained across calls)
        self._messages: List[Dict[str, Any]] = []
        self._sdk_client = None
    
    def _default_system_prompt(self) -> str:
        return """You are an AI assistant specialized in incident response and DevOps.
You help users manage incidents, analyze alerts, and troubleshoot issues.

When deciding how to respond:
1. If the user's request requires looking up data or taking action, use the appropriate tools
2. If the user wants general information or explanation, respond directly
3. Be concise but thorough in your responses

## Available Tools
- get_incidents_by_time: Fetch incidents within a time range
- get_incident_by_id: Get detailed incident information
- get_incident_stats: Get incident statistics
- get_current_time: Get current time for time-based queries
- search_incidents: Full-text search for incidents"""

    def set_messages(self, messages: List[Dict[str, Any]]) -> None:
        """Set conversation history."""
        self._messages = messages.copy()
    
    def get_messages(self) -> List[Dict[str, Any]]:
        """Get current conversation history."""
        return self._messages.copy()
    
    def clear_messages(self) -> None:
        """Clear conversation history."""
        self._messages = []
        self._sdk_client = None

    async def process(
        self,
        prompt: str,
        auth_token: str = None,
        org_id: str = None,
        project_id: str = None,
    ) -> SDKOrchestratorResult:
        """
        Process user prompt using Claude Agent SDK.
        
        This method:
        1. Sets up auth context for tools
        2. Creates SDK client with MCP servers
        3. Sends prompt and processes response
        4. Collects tool executions and text response
        5. Returns result for streaming layer
        
        Args:
            prompt: User's input message
            auth_token: JWT token for API calls
            org_id: Organization ID for tenant isolation
            project_id: Project ID for filtering
        
        Returns:
            SDKOrchestratorResult with tool executions and context
        """
        try:
            from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
            from tools.incidents import (
                create_incident_tools_server,
                set_auth_token,
                set_org_id,
                set_project_id,
            )
            
            # Set auth context for tools
            if auth_token:
                set_auth_token(auth_token)
            if org_id:
                set_org_id(org_id)
            if project_id:
                set_project_id(project_id)
            
            # Create incident tools MCP server
            incident_tools_server = create_incident_tools_server()
            
            # Merge with any external MCP servers
            all_mcp_servers = {"incident_tools": incident_tools_server}
            all_mcp_servers.update(self.mcp_servers)
            
            # Configure SDK options
            options = ClaudeAgentOptions(
                permission_mode=self.permission_mode,
                model=self.model,
                mcp_servers=all_mcp_servers,
                max_turns=self.max_turns,
            )
            
            # Track results
            tool_executions: List[ToolExecution] = []
            text_response = ""
            thinking = None
            
            # Add user message to history
            self._messages.append({
                "role": "user",
                "content": prompt
            })
            
            # Process with SDK
            async with ClaudeSDKClient(options=options) as client:
                # Send the prompt
                await client.query(prompt=prompt)
                
                # Process response blocks
                async for message in client.receive_response():
                    logger.debug(f"SDK message: {type(message)}")
                    
                    if hasattr(message, 'content'):
                        for block in message.content:
                            # Text response
                            if hasattr(block, 'text'):
                                text_response += block.text
                            
                            # Thinking block
                            elif hasattr(block, 'thinking'):
                                thinking = block.thinking
                            
                            # Tool use block
                            elif hasattr(block, 'type') and block.type == "tool_use":
                                # SDK executes tools automatically
                                # We just record that it happened
                                tool_executions.append(ToolExecution(
                                    id=block.id,
                                    name=block.name,
                                    input=block.input,
                                    result="",  # Will be filled by SDK
                                ))
                            
                            # Tool result block
                            elif hasattr(block, 'type') and block.type == "tool_result":
                                # Match result to execution
                                for exec in tool_executions:
                                    if exec.id == block.tool_use_id:
                                        exec.result = str(block.content)
                                        exec.is_error = getattr(block, 'is_error', False)
                                        break
            
            # Update message history with assistant response
            self._messages.append({
                "role": "assistant",
                "content": text_response
            })
            
            # Determine action type
            if tool_executions:
                action_type = ActionType.STREAM_AFTER_TOOLS
            else:
                action_type = ActionType.STREAM_RESPONSE
            
            return SDKOrchestratorResult(
                action_type=action_type,
                tool_executions=tool_executions,
                text_response=text_response,
                thinking=thinking,
                messages=self._messages.copy(),
            )
            
        except ImportError as e:
            logger.error(f"Claude Agent SDK not available: {e}")
            return SDKOrchestratorResult(
                action_type=ActionType.ERROR,
                error=f"Claude Agent SDK not available: {e}"
            )
        except Exception as e:
            logger.error(f"SDK orchestrator error: {e}", exc_info=True)
            return SDKOrchestratorResult(
                action_type=ActionType.ERROR,
                error=str(e)
            )


# Convenience function to create orchestrator with incident tools
def create_sdk_orchestrator(
    model: str = "claude-sonnet-4-20250514",
    external_mcp_servers: Dict[str, Any] = None,
) -> SDKOrchestrator:
    """
    Create an SDK orchestrator with incident tools.
    
    Args:
        model: Model to use
        external_mcp_servers: Additional MCP servers (Coralogix, etc.)
    
    Returns:
        Configured SDKOrchestrator
    """
    return SDKOrchestrator(
        model=model,
        mcp_servers=external_mcp_servers or {},
    )
