"""
Hybrid Agent - Combines SDK Orchestration with Token-Level Streaming.

This is the main agent class that provides:
1. Claude Agent SDK capabilities (tools, MCP, permissions, planning)
2. Direct Anthropic API token-level streaming (smooth UX)

Architecture:
    User Message
         │
         ▼
    ┌─────────────────────┐
    │   Orchestrator      │  ◄── Uses SDK features (planning, tools)
    │   (plan action)     │
    └─────────┬───────────┘
              │
              ▼
    ┌─────────────────────┐
    │   Action Router     │
    └─────────┬───────────┘
              │
    ┌─────────┴─────────┬──────────────────┐
    │                   │                   │
    ▼                   ▼                   ▼
  STREAM           EXECUTE_TOOLS      ERROR
    │                   │
    ▼                   ▼
┌─────────────┐   ┌─────────────┐
│ Direct API  │   │ Tool Exec   │
│ (tokens)    │   │ (SDK/MCP)   │
└──────┬──────┘   └──────┬──────┘
       │                 │
       ▼                 ▼
    output_queue ◄───── Stream Results

"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import anthropic
from anthropic.types import (
    ContentBlockDeltaEvent,
    ContentBlockStartEvent,
    ContentBlockStopEvent,
)

from core.base_agent import BaseAgent, AgentConfig, AgentFactory
from core.message_history import MessageHistory
from .orchestrator import (
    AgentOrchestrator,
    OrchestratorAction,
    ActionType,
    ToolAction,
)

logger = logging.getLogger(__name__)


@dataclass
class HybridAgentConfig(AgentConfig):
    """
    Extended configuration for HybridAgent.
    
    Includes both streaming and SDK configuration options.
    """
    
    # Streaming settings
    streaming_model: str = "claude-sonnet-4-20250514"  # Model for streaming responses
    
    # Planning settings
    planning_model: str = "claude-sonnet-4-20250514"  # Model for orchestration/planning
    max_planning_tokens: int = 1024  # Limit planning phase to save latency
    
    # SDK features
    mcp_servers: Dict[str, Any] = field(default_factory=dict)
    permission_callback: Optional[Callable] = None
    
    # Hybrid behavior
    always_plan: bool = False  # If True, always use orchestrator first
    tool_threshold: float = 0.8  # Confidence threshold for tool use


class HybridAgent(BaseAgent):
    """
    Hybrid agent combining SDK orchestration with token-level streaming.
    
    Key Benefits:
    - Token-by-token streaming for smooth UI (direct Anthropic API)
    - Full tool orchestration with permissions (Claude Agent SDK patterns)
    - MCP server support for external integrations
    - Multi-turn conversation with history management
    - Interrupt support during streaming
    
    Usage:
        config = HybridAgentConfig(
            tools=INCIDENT_TOOLS,
            mcp_servers={"coralogix": {...}},
        )
        agent = HybridAgent(config=config)
        
        response = await agent.process_message(
            prompt="Show me recent incidents",
            output_queue=queue,
            tool_executor=executor
        )
    """
    
    def __init__(
        self,
        config: HybridAgentConfig = None,
        api_key: str = None,
    ):
        """
        Initialize the hybrid agent.
        
        Args:
            config: Agent configuration
            api_key: Anthropic API key (defaults to env var)
        """
        if config is None:
            config = HybridAgentConfig()
        
        super().__init__(config)
        
        self.config: HybridAgentConfig = config
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        
        # Direct Anthropic client for streaming
        self.client = anthropic.AsyncAnthropic(api_key=self.api_key)
        
        # Message history
        self._history = MessageHistory()
        
        # Orchestrator for planning (lazy init)
        self._orchestrator: Optional[AgentOrchestrator] = None
    
    @property
    def orchestrator(self) -> AgentOrchestrator:
        """Get or create the orchestrator."""
        if self._orchestrator is None:
            self._orchestrator = AgentOrchestrator(
                model=self.config.planning_model,
                system_prompt=self.config.system_prompt,
                tools=self.config.tools,
                mcp_servers=self.config.mcp_servers,
                permission_callback=self.config.permission_callback,
                max_planning_tokens=self.config.max_planning_tokens,
            )
        return self._orchestrator
    
    @property
    def messages(self) -> List[Dict[str, Any]]:
        """Get messages in API format."""
        return self._history.to_api_format()
    
    async def process_message(
        self,
        prompt: str,
        output_queue: asyncio.Queue,
        tool_executor: Optional[Callable[[str, Dict], Any]] = None,
    ) -> str:
        """
        Process a user message with hybrid approach.
        
        Flow:
        1. Check if tools might be needed (quick analysis)
        2. If tools likely needed → use orchestrator for planning + execution
        3. Stream the final response via direct API (token-level)
        
        Args:
            prompt: User's input message
            output_queue: Queue for streaming events to UI
            tool_executor: Function to execute tools
        
        Returns:
            Complete assistant response text
        """
        self.reset_interrupt()
        
        # Validate and fix any corrupted history
        self._history.validate_and_repair()
        
        try:
            # Determine if we should use orchestrator (tools likely needed)
            use_orchestrator = self._should_use_orchestrator(prompt)
            
            if use_orchestrator and tool_executor:
                return await self._process_with_orchestrator(
                    prompt, output_queue, tool_executor
                )
            else:
                return await self._process_direct_streaming(
                    prompt, output_queue, tool_executor
                )
                
        except Exception as e:
            logger.error(f"HybridAgent error: {e}", exc_info=True)
            await output_queue.put({
                "type": "error",
                "error": str(e)
            })
            return ""
    
    def _should_use_orchestrator(self, prompt: str) -> bool:
        """
        Decide if the orchestrator should be used for this prompt.
        
        Uses heuristics to determine if tools are likely needed:
        - Keywords indicating data lookup
        - Keywords indicating actions
        - Questions about specific incidents/metrics
        
        This avoids the latency of planning when simple responses suffice.
        """
        if self.config.always_plan:
            return True
        
        # If no tools configured, no point in orchestrating
        if not self.config.tools:
            return False
        
        prompt_lower = prompt.lower()
        
        # Keywords that suggest tool usage
        tool_keywords = [
            # Incident management
            "incident", "incidents", "alert", "alerts",
            "acknowledge", "resolve", "status",
            # Data lookup
            "show me", "get", "fetch", "list", "find",
            "what are", "how many", "statistics", "stats",
            # Actions
            "create", "update", "delete", "run",
            # Time-based queries
            "recent", "latest", "last", "past",
            # MCP/External services
            "logs", "coralogix", "confluence", "search",
        ]
        
        for keyword in tool_keywords:
            if keyword in prompt_lower:
                return True
        
        return False
    
    async def _process_with_orchestrator(
        self,
        prompt: str,
        output_queue: asyncio.Queue,
        tool_executor: Callable[[str, Dict], Any],
    ) -> str:
        """
        Process using orchestrator for tool planning/execution.
        
        1. Orchestrator plans and executes tools
        2. Stream the final response with tool context
        """
        # Sync orchestrator messages with our history
        self.orchestrator.set_messages(self._history.to_api_format())
        
        # Plan and execute tools
        action = await self.orchestrator.plan(prompt, tool_executor)
        
        # Handle different action types
        if action.action_type == ActionType.ERROR:
            await output_queue.put({
                "type": "error",
                "error": action.error
            })
            return ""
        
        # Send any thinking to UI
        if action.thinking:
            await output_queue.put({
                "type": "thinking",
                "content": action.thinking
            })
        
        # Send tool events to UI
        for tool in action.tools:
            await output_queue.put({
                "type": "tool_use",
                "id": tool.id,
                "name": tool.name,
                "input": tool.input
            })
        
        for result in action.tool_results:
            await output_queue.put({
                "type": "tool_result",
                "tool_use_id": result["tool_use_id"],
                "content": result["result"],
                "is_error": result.get("is_error", False)
            })
        
        # Update our history from orchestrator
        self._history = MessageHistory(messages=self.orchestrator.get_messages())
        
        # Now stream the final response
        if action.action_type == ActionType.STREAM_AFTER_TOOLS:
            # Stream response incorporating tool results
            return await self._stream_continuation(output_queue, tool_executor)
        elif action.action_type == ActionType.STREAM_RESPONSE:
            # Direct response (might already have text from planning)
            if action.partial_text:
                # Send the planned text as stream
                await output_queue.put({
                    "type": "delta",
                    "content": action.partial_text
                })
                await output_queue.put({"type": "complete"})
                return action.partial_text
            else:
                return await self._stream_response(prompt, output_queue, tool_executor)
        
        return ""
    
    async def _process_direct_streaming(
        self,
        prompt: str,
        output_queue: asyncio.Queue,
        tool_executor: Optional[Callable[[str, Dict], Any]] = None,
    ) -> str:
        """
        Process with direct token-level streaming (no orchestrator).
        
        This is the fast path when tools are unlikely to be needed.
        If tools ARE used, handles them inline.
        """
        self._history.add_user_message(prompt)
        return await self._stream_response(prompt, output_queue, tool_executor)
    
    async def _stream_response(
        self,
        prompt: str,
        output_queue: asyncio.Queue,
        tool_executor: Optional[Callable[[str, Dict], Any]] = None,
    ) -> str:
        """
        Stream a response using direct Anthropic API (token-level).
        
        This provides smooth, token-by-token streaming to the UI.
        Handles tool calls inline if they occur.
        """
        full_response = ""
        
        try:
            request_params = {
                "model": self.config.streaming_model,
                "max_tokens": self.config.max_tokens,
                "system": self.config.system_prompt,
                "messages": self._history.to_api_format(),
            }
            
            if self.config.tools:
                request_params["tools"] = self.config.tools
            
            async with self.client.messages.stream(**request_params) as stream:
                current_tool_use = None
                tool_input_json = ""
                pending_tool_results = []
                
                async for event in stream:
                    # Check for interrupt
                    if self._interrupted:
                        logger.info("Stream interrupted")
                        await output_queue.put({"type": "interrupted"})
                        break
                    
                    # Handle events
                    if isinstance(event, ContentBlockStartEvent):
                        content_block = event.content_block
                        if hasattr(content_block, 'type') and content_block.type == "tool_use":
                            current_tool_use = {
                                "id": content_block.id,
                                "name": content_block.name,
                            }
                            tool_input_json = ""
                    
                    elif isinstance(event, ContentBlockDeltaEvent):
                        delta = event.delta
                        
                        if hasattr(delta, 'text'):
                            text = delta.text
                            full_response += text
                            await output_queue.put({
                                "type": "delta",
                                "content": text
                            })
                        elif hasattr(delta, 'partial_json'):
                            tool_input_json += delta.partial_json
                    
                    elif isinstance(event, ContentBlockStopEvent):
                        if current_tool_use and tool_input_json:
                            try:
                                tool_input = json.loads(tool_input_json)
                                current_tool_use["input"] = tool_input
                                
                                # Send tool_use to UI
                                await output_queue.put({
                                    "type": "tool_use",
                                    "id": current_tool_use["id"],
                                    "name": current_tool_use["name"],
                                    "input": tool_input
                                })
                                
                                # Execute tool
                                if tool_executor:
                                    tool_result = await self._execute_tool(
                                        current_tool_use["name"],
                                        tool_input,
                                        tool_executor
                                    )
                                    
                                    await output_queue.put({
                                        "type": "tool_result",
                                        "tool_use_id": current_tool_use["id"],
                                        "content": tool_result,
                                        "is_error": False
                                    })
                                    
                                    pending_tool_results.append({
                                        "tool_use_id": current_tool_use["id"],
                                        "result": tool_result
                                    })
                                    
                            except json.JSONDecodeError as e:
                                logger.error(f"Tool input parse error: {e}")
                                if tool_executor and current_tool_use:
                                    error_result = f"Error parsing tool input: {e}"
                                    await output_queue.put({
                                        "type": "tool_result",
                                        "tool_use_id": current_tool_use["id"],
                                        "content": error_result,
                                        "is_error": True
                                    })
                                    pending_tool_results.append({
                                        "tool_use_id": current_tool_use["id"],
                                        "result": error_result
                                    })
                            finally:
                                current_tool_use = None
                                tool_input_json = ""
                
                # Get final message
                final_message = await stream.get_final_message()
                
                # Handle tool continuation
                if final_message.stop_reason == "tool_use" and tool_executor:
                    # Add assistant message with tool_use
                    assistant_content = self._convert_content_blocks(final_message.content)
                    self._history.add_assistant_with_content(assistant_content)
                    
                    # Add tool results
                    self._history.add_tool_results(pending_tool_results)
                    
                    # Continue conversation
                    continued = await self._stream_continuation(output_queue, tool_executor)
                    full_response += continued
                elif not pending_tool_results:
                    # Simple text response
                    self._history.add_assistant_message(full_response)
            
            # Send complete
            await output_queue.put({"type": "complete"})
            return full_response
            
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            await output_queue.put({"type": "error", "error": str(e)})
            return ""
        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            await output_queue.put({"type": "error", "error": str(e)})
            return ""
    
    async def _stream_continuation(
        self,
        output_queue: asyncio.Queue,
        tool_executor: Callable,
    ) -> str:
        """Stream continuation after tool execution."""
        full_response = ""
        
        self._history.validate_and_repair()
        
        try:
            request_params = {
                "model": self.config.streaming_model,
                "max_tokens": self.config.max_tokens,
                "system": self.config.system_prompt,
                "messages": self._history.to_api_format(),
            }
            
            if self.config.tools:
                request_params["tools"] = self.config.tools
            
            async with self.client.messages.stream(**request_params) as stream:
                current_tool_use = None
                tool_input_json = ""
                pending_tool_results = []
                
                async for event in stream:
                    if self._interrupted:
                        break
                    
                    if isinstance(event, ContentBlockStartEvent):
                        content_block = event.content_block
                        if hasattr(content_block, 'type') and content_block.type == "tool_use":
                            current_tool_use = {
                                "id": content_block.id,
                                "name": content_block.name,
                            }
                            tool_input_json = ""
                    
                    elif isinstance(event, ContentBlockDeltaEvent):
                        delta = event.delta
                        if hasattr(delta, 'text'):
                            text = delta.text
                            full_response += text
                            await output_queue.put({
                                "type": "delta",
                                "content": text
                            })
                        elif hasattr(delta, 'partial_json'):
                            tool_input_json += delta.partial_json
                    
                    elif isinstance(event, ContentBlockStopEvent):
                        if current_tool_use and tool_input_json:
                            try:
                                tool_input = json.loads(tool_input_json)
                                current_tool_use["input"] = tool_input
                                
                                await output_queue.put({
                                    "type": "tool_use",
                                    "id": current_tool_use["id"],
                                    "name": current_tool_use["name"],
                                    "input": tool_input
                                })
                                
                                if tool_executor:
                                    tool_result = await self._execute_tool(
                                        current_tool_use["name"],
                                        tool_input,
                                        tool_executor
                                    )
                                    await output_queue.put({
                                        "type": "tool_result",
                                        "tool_use_id": current_tool_use["id"],
                                        "content": tool_result,
                                        "is_error": False
                                    })
                                    pending_tool_results.append({
                                        "tool_use_id": current_tool_use["id"],
                                        "result": tool_result
                                    })
                            except json.JSONDecodeError:
                                pass
                            finally:
                                current_tool_use = None
                                tool_input_json = ""
                
                final_message = await stream.get_final_message()
                
                if final_message.stop_reason == "tool_use" and tool_executor:
                    assistant_content = self._convert_content_blocks(final_message.content)
                    self._history.add_assistant_with_content(assistant_content)
                    self._history.add_tool_results(pending_tool_results)
                    
                    # Recursive continuation
                    continued = await self._stream_continuation(output_queue, tool_executor)
                    full_response += continued
                else:
                    if full_response:
                        self._history.add_assistant_message(full_response)
            
            return full_response
            
        except Exception as e:
            logger.error(f"Continuation error: {e}", exc_info=True)
            recovery = "I encountered an error processing the results."
            self._history.add_assistant_message(recovery)
            await output_queue.put({"type": "delta", "content": recovery})
            return recovery
    
    async def _execute_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        executor: Callable,
    ) -> str:
        """Execute a tool and return result."""
        try:
            if asyncio.iscoroutinefunction(executor):
                result = await executor(tool_name, tool_input)
            else:
                result = executor(tool_name, tool_input)
            return str(result) if result is not None else "Tool executed successfully"
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return f"Error: {str(e)}"
    
    def _convert_content_blocks(self, blocks: List[Any]) -> List[Dict[str, Any]]:
        """Convert API content blocks to dict format."""
        content = []
        for block in blocks:
            if hasattr(block, 'text'):
                content.append({"type": "text", "text": block.text})
            elif hasattr(block, 'type') and block.type == "tool_use":
                content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input
                })
        return content
    
    def clear_history(self) -> None:
        """Clear conversation history."""
        self._history.clear()
        if self._orchestrator:
            self._orchestrator.clear_messages()
    
    def get_history(self) -> List[Dict[str, Any]]:
        """Get conversation history."""
        return self._history.to_api_format()
    
    def set_history(self, messages: List[Dict[str, Any]]) -> None:
        """Set conversation history (for resume support)."""
        self._history = MessageHistory(messages=messages)
        if self._orchestrator:
            self._orchestrator.set_messages(messages)


# Register with AgentFactory
AgentFactory.register("hybrid", HybridAgent)
