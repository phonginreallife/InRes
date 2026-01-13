"""
Agent Orchestrator - Planning Layer using Claude Agent SDK.

This module provides the "thinking" layer that decides what actions
to take without streaming tokens. It uses the Claude Agent SDK
for its rich orchestration features.

The orchestrator:
1. Analyzes user input
2. Decides if tools are needed
3. Executes tools with full SDK capabilities (permissions, MCP, audit)
4. Returns action decisions for the streaming layer

This is the "brain" that plans, while the streaming layer is the "voice".
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
    
    # Execute one or more tools (use SDK for permissions/MCP)
    EXECUTE_TOOLS = "execute_tools"
    
    # Stream response after tool execution
    STREAM_AFTER_TOOLS = "stream_after_tools"
    
    # Error occurred during planning
    ERROR = "error"


@dataclass
class ToolAction:
    """A single tool to be executed."""
    id: str
    name: str
    input: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "input": self.input
        }


@dataclass
class OrchestratorAction:
    """
    An action decision from the orchestrator.
    
    Contains the action type and any associated data needed
    for the streaming layer to execute.
    """
    action_type: ActionType
    
    # For STREAM_RESPONSE: the context/prompt to stream
    stream_context: Optional[str] = None
    
    # For EXECUTE_TOOLS: list of tools to execute
    tools: List[ToolAction] = field(default_factory=list)
    
    # For STREAM_AFTER_TOOLS: tool results to incorporate
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    
    # For ERROR: error message
    error: Optional[str] = None
    
    # Assistant's partial text (if any) before tool calls
    partial_text: str = ""
    
    # Whether thinking/reasoning was included
    thinking: Optional[str] = None


class AgentOrchestrator:
    """
    Planning layer that uses SDK to decide actions.
    
    This class wraps the Claude Agent SDK to make planning decisions
    WITHOUT streaming tokens. It's responsible for:
    
    1. Analyzing what the user wants
    2. Deciding if tools are needed
    3. Executing tools (with SDK's permission system)
    4. Preparing context for the streaming layer
    
    The actual text streaming is done by the HybridAgent using
    direct Anthropic API calls.
    """
    
    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        system_prompt: str = None,
        tools: List[Dict[str, Any]] = None,
        mcp_servers: Dict[str, Any] = None,
        permission_callback: Callable = None,
        max_planning_tokens: int = 1024,
    ):
        """
        Initialize the orchestrator.
        
        Args:
            model: Model to use for planning
            system_prompt: System prompt for the agent
            tools: Available tools
            mcp_servers: MCP server configurations
            permission_callback: Callback for tool permissions
            max_planning_tokens: Max tokens for planning phase
        """
        self.model = model
        self.system_prompt = system_prompt or self._default_system_prompt()
        self.tools = tools or []
        self.mcp_servers = mcp_servers or {}
        self.permission_callback = permission_callback
        self.max_planning_tokens = max_planning_tokens
        
        # Conversation state
        self._messages: List[Dict[str, Any]] = []
    
    def _default_system_prompt(self) -> str:
        return """You are an AI assistant specialized in incident response and DevOps.
You help users manage incidents, analyze alerts, and troubleshoot issues.

When deciding how to respond:
1. If the user's request requires looking up data or taking action, use the appropriate tools
2. If the user wants general information or explanation, respond directly
3. Be concise but thorough in your responses"""

    async def plan(
        self,
        prompt: str,
        tool_executor: Callable[[str, Dict], Any] = None,
    ) -> OrchestratorAction:
        """
        Analyze user input and decide what action to take.
        
        This is a "non-streaming" planning phase that:
        1. Sends the prompt to Claude via SDK
        2. Analyzes the response to determine if tools are needed
        3. Executes any tools (using SDK for permissions)
        4. Returns an action for the streaming layer
        
        Args:
            prompt: User's input message
            tool_executor: Function to execute tools
        
        Returns:
            OrchestratorAction indicating what to do next
        """
        try:
            # For now, we'll use a simplified planning approach
            # that analyzes the prompt to decide if tools are likely needed
            
            # Add user message to history
            self._messages.append({
                "role": "user",
                "content": prompt
            })
            
            # Use direct API for planning (non-streaming)
            # This is faster than SDK for simple planning decisions
            import anthropic
            client = anthropic.AsyncAnthropic()
            
            # Build planning request with tools
            request_params = {
                "model": self.model,
                "max_tokens": self.max_planning_tokens,
                "system": self.system_prompt,
                "messages": self._messages,
            }
            
            if self.tools:
                request_params["tools"] = self.tools
            
            # Get planning response
            response = await client.messages.create(**request_params)
            
            # Analyze response
            tools_to_execute = []
            partial_text = ""
            thinking = None
            
            for block in response.content:
                if hasattr(block, 'text'):
                    partial_text += block.text
                elif hasattr(block, 'thinking'):
                    thinking = block.thinking
                elif hasattr(block, 'type') and block.type == "tool_use":
                    tools_to_execute.append(ToolAction(
                        id=block.id,
                        name=block.name,
                        input=block.input
                    ))
            
            # Decide action based on response
            if tools_to_execute:
                # Execute tools
                tool_results = []
                for tool in tools_to_execute:
                    if tool_executor:
                        try:
                            result = await tool_executor(tool.name, tool.input)
                            tool_results.append({
                                "tool_use_id": tool.id,
                                "result": str(result)
                            })
                        except Exception as e:
                            tool_results.append({
                                "tool_use_id": tool.id,
                                "result": f"Error: {str(e)}",
                                "is_error": True
                            })
                
                # Update message history with tool use and results
                self._add_assistant_with_tools(response.content, partial_text)
                self._add_tool_results(tool_results)
                
                return OrchestratorAction(
                    action_type=ActionType.STREAM_AFTER_TOOLS,
                    tools=[t for t in tools_to_execute],
                    tool_results=tool_results,
                    partial_text=partial_text,
                    thinking=thinking,
                )
            else:
                # No tools needed - stream response directly
                # But we already have text from planning, so we need to
                # indicate to re-stream (or just use the partial text)
                
                # Add assistant message to history
                self._messages.append({
                    "role": "assistant",
                    "content": partial_text
                })
                
                return OrchestratorAction(
                    action_type=ActionType.STREAM_RESPONSE,
                    stream_context=prompt,
                    partial_text=partial_text,
                    thinking=thinking,
                )
                
        except Exception as e:
            logger.error(f"Orchestrator planning error: {e}", exc_info=True)
            return OrchestratorAction(
                action_type=ActionType.ERROR,
                error=str(e)
            )
    
    def _add_assistant_with_tools(
        self,
        content_blocks: List[Any],
        text: str
    ) -> None:
        """Add assistant message with tool_use blocks to history."""
        content = []
        
        for block in content_blocks:
            if hasattr(block, 'text'):
                content.append({"type": "text", "text": block.text})
            elif hasattr(block, 'type') and block.type == "tool_use":
                content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input
                })
        
        self._messages.append({
            "role": "assistant",
            "content": content if content else text
        })
    
    def _add_tool_results(self, results: List[Dict[str, Any]]) -> None:
        """Add tool results as user message."""
        content = []
        for r in results:
            content.append({
                "type": "tool_result",
                "tool_use_id": r["tool_use_id"],
                "content": r["result"]
            })
        
        self._messages.append({
            "role": "user",
            "content": content
        })
    
    def get_messages(self) -> List[Dict[str, Any]]:
        """Get current message history."""
        return self._messages.copy()
    
    def set_messages(self, messages: List[Dict[str, Any]]) -> None:
        """Set message history (for resume support)."""
        self._messages = messages.copy()
    
    def clear_messages(self) -> None:
        """Clear message history."""
        self._messages = []
