"""
SDK Hybrid Agent - Claude Agent SDK + Token-Level Streaming.

This agent provides the best of both worlds:
1. Claude Agent SDK for planning, tools, MCP, and permissions
2. Direct Anthropic API for smooth token-level streaming

Architecture:
    User Message
         │
         ▼
    ┌─────────────────────────────────────────────────┐
    │              SDKOrchestrator                     │
    │  ┌───────────────────────────────────────────┐  │
    │  │         Claude Agent SDK                   │  │
    │  │  • Planning & decision making              │  │
    │  │  • Tool execution via @tool decorators     │  │
    │  │  • MCP server integration                  │  │
    │  │  • Permission handling                     │  │
    │  └───────────────────────────────────────────┘  │
    └─────────────────────┬───────────────────────────┘
                          │
                          │ Tool results + context
                          ▼
    ┌─────────────────────────────────────────────────┐
    │           Direct Anthropic API                   │
    │  ┌───────────────────────────────────────────┐  │
    │  │     client.messages.stream()              │  │
    │  │  • Token-by-token streaming               │  │
    │  │  • Smooth UI updates                      │  │
    │  └───────────────────────────────────────────┘  │
    └─────────────────────┬───────────────────────────┘
                          │
                          ▼
                    output_queue → WebSocket → UI
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
from .sdk_orchestrator import (
    SDKOrchestrator,
    SDKOrchestratorResult,
    ActionType,
    ToolExecution,
)

logger = logging.getLogger(__name__)


@dataclass
class SDKHybridAgentConfig(AgentConfig):
    """
    Configuration for SDK Hybrid Agent.
    
    Combines SDK and streaming settings.
    """
    
    # Model settings
    streaming_model: str = "claude-sonnet-4-20250514"  # For final streaming
    sdk_model: str = "claude-sonnet-4-20250514"  # For SDK orchestration
    
    # SDK settings
    mcp_servers: Dict[str, Any] = field(default_factory=dict)
    permission_mode: str = "default"  # acceptEdits, bypassPermissions, default, dontAsk, plan
    max_turns: int = 10
    
    # Behavior settings
    always_use_sdk: bool = True  # Always route through SDK for tools
    stream_final_response: bool = True  # Stream the final response token-by-token


class SDKHybridAgent(BaseAgent):
    """
    Hybrid agent using Claude Agent SDK for tools and direct API for streaming.
    
    This is the recommended agent for production use, providing:
    - Full SDK tool capabilities via @tool decorators
    - MCP server support for external integrations
    - Token-level streaming for smooth UI
    - Multi-turn conversation support
    - Interrupt handling
    
    Usage:
        config = SDKHybridAgentConfig(
            mcp_servers={"coralogix": coralogix_server},
        )
        agent = SDKHybridAgent(config=config)
        
        response = await agent.process_message(
            prompt="Show me recent incidents",
            output_queue=queue,
            auth_token=token,
            org_id=org_id,
        )
    """
    
    def __init__(
        self,
        config: SDKHybridAgentConfig = None,
        api_key: str = None,
    ):
        """
        Initialize the SDK hybrid agent.
        
        Args:
            config: Agent configuration
            api_key: Anthropic API key (defaults to env var)
        """
        if config is None:
            config = SDKHybridAgentConfig()
        
        super().__init__(config)
        
        self.config: SDKHybridAgentConfig = config
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        
        # Direct Anthropic client for streaming
        self.client = anthropic.AsyncAnthropic(api_key=self.api_key)
        
        # Message history for streaming layer
        self._history = MessageHistory()
        
        # SDK orchestrator (lazy init)
        self._orchestrator: Optional[SDKOrchestrator] = None
        
        # Auth context (set per session)
        self._auth_token: Optional[str] = None
        self._org_id: Optional[str] = None
        self._project_id: Optional[str] = None
    
    @property
    def orchestrator(self) -> SDKOrchestrator:
        """Get or create the SDK orchestrator."""
        if self._orchestrator is None:
            self._orchestrator = SDKOrchestrator(
                model=self.config.sdk_model,
                system_prompt=self.config.system_prompt,
                mcp_servers=self.config.mcp_servers,
                permission_mode=self.config.permission_mode,
                max_turns=self.config.max_turns,
            )
        return self._orchestrator
    
    def set_auth_context(
        self,
        auth_token: str = None,
        org_id: str = None,
        project_id: str = None,
    ) -> None:
        """
        Set authentication context for tool execution.
        
        This should be called at the start of each session.
        """
        self._auth_token = auth_token
        self._org_id = org_id
        self._project_id = project_id
    
    @property
    def messages(self) -> List[Dict[str, Any]]:
        """Get messages in API format."""
        return self._history.to_api_format()
    
    async def process_message(
        self,
        prompt: str,
        output_queue: asyncio.Queue,
        tool_executor: Optional[Callable[[str, Dict], Any]] = None,
        auth_token: str = None,
        org_id: str = None,
        project_id: str = None,
    ) -> str:
        """
        Process a user message with SDK + streaming hybrid approach.
        
        Flow:
        1. Send prompt to SDK orchestrator (planning + tool execution)
        2. Get tool results and context from SDK
        3. Stream final response via direct Anthropic API
        
        Args:
            prompt: User's input message
            output_queue: Queue for streaming events to UI
            tool_executor: Unused (SDK handles tools internally)
            auth_token: JWT token for API calls
            org_id: Organization ID for tenant isolation
            project_id: Project ID for filtering
        
        Returns:
            Complete assistant response text
        """
        self.reset_interrupt()
        
        # Use provided auth or fall back to stored context
        auth_token = auth_token or self._auth_token
        org_id = org_id or self._org_id
        project_id = project_id or self._project_id
        
        try:
            # Step 1: Process with SDK orchestrator
            logger.info(f"Processing with SDK orchestrator: {prompt[:50]}...")
            
            sdk_result = await self.orchestrator.process(
                prompt=prompt,
                auth_token=auth_token,
                org_id=org_id,
                project_id=project_id,
            )
            
            # Handle errors
            if sdk_result.action_type == ActionType.ERROR:
                await output_queue.put({
                    "type": "error",
                    "error": sdk_result.error
                })
                return ""
            
            # Step 2: Send tool events to UI
            if sdk_result.tool_executions:
                await self._send_tool_events(output_queue, sdk_result.tool_executions)
            
            # Send thinking if present
            if sdk_result.thinking:
                await output_queue.put({
                    "type": "thinking",
                    "content": sdk_result.thinking
                })
            
            # Step 3: Stream final response
            if self.config.stream_final_response and sdk_result.action_type == ActionType.STREAM_AFTER_TOOLS:
                # SDK executed tools, now stream the final response with context
                return await self._stream_with_tool_context(
                    prompt=prompt,
                    sdk_result=sdk_result,
                    output_queue=output_queue,
                )
            else:
                # SDK already has the response, send it as a stream
                if sdk_result.text_response:
                    await output_queue.put({
                        "type": "delta",
                        "content": sdk_result.text_response
                    })
                    await output_queue.put({"type": "complete"})
                    
                    # Update history
                    self._history.add_user_message(prompt)
                    self._history.add_assistant_message(sdk_result.text_response)
                    
                    return sdk_result.text_response
                else:
                    # Stream a fresh response
                    return await self._stream_response(prompt, output_queue)
        
        except Exception as e:
            logger.error(f"SDKHybridAgent error: {e}", exc_info=True)
            await output_queue.put({
                "type": "error",
                "error": str(e)
            })
            return ""
    
    async def _send_tool_events(
        self,
        output_queue: asyncio.Queue,
        tool_executions: List[ToolExecution],
    ) -> None:
        """Send tool use and result events to the output queue."""
        for tool in tool_executions:
            # Send tool use event
            await output_queue.put({
                "type": "tool_use",
                "id": tool.id,
                "name": tool.name,
                "input": tool.input
            })
            
            # Send tool result event
            await output_queue.put({
                "type": "tool_result",
                "tool_use_id": tool.id,
                "content": tool.result,
                "is_error": tool.is_error
            })
    
    async def _stream_with_tool_context(
        self,
        prompt: str,
        sdk_result: SDKOrchestratorResult,
        output_queue: asyncio.Queue,
    ) -> str:
        """
        Stream a response that incorporates tool results.
        
        Uses the messages from SDK (which include tool uses/results)
        to generate a final streamed response.
        """
        full_response = ""
        
        try:
            # Build messages with tool context
            messages = self._build_messages_with_tools(prompt, sdk_result)
            
            request_params = {
                "model": self.config.streaming_model,
                "max_tokens": self.config.max_tokens,
                "system": self.config.system_prompt,
                "messages": messages,
            }
            
            async with self.client.messages.stream(**request_params) as stream:
                async for event in stream:
                    if self._interrupted:
                        await output_queue.put({"type": "interrupted"})
                        break
                    
                    if isinstance(event, ContentBlockDeltaEvent):
                        if hasattr(event.delta, 'text'):
                            text = event.delta.text
                            full_response += text
                            await output_queue.put({
                                "type": "delta",
                                "content": text
                            })
            
            await output_queue.put({"type": "complete"})
            
            # Update history
            self._history.add_user_message(prompt)
            self._history.add_assistant_message(full_response)
            
            return full_response
            
        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            await output_queue.put({
                "type": "error",
                "error": str(e)
            })
            return full_response
    
    def _build_messages_with_tools(
        self,
        prompt: str,
        sdk_result: SDKOrchestratorResult,
    ) -> List[Dict[str, Any]]:
        """
        Build messages array that includes tool context.
        
        Format:
        1. Previous history
        2. User message
        3. Assistant response with tool_use blocks
        4. Tool result blocks
        5. (API will generate final response)
        """
        messages = self._history.to_api_format()
        
        # Add user message
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        # Build assistant message with tool uses
        if sdk_result.tool_executions:
            assistant_content = []
            
            # Add any partial text
            if sdk_result.text_response:
                assistant_content.append({
                    "type": "text",
                    "text": sdk_result.text_response
                })
            
            # Add tool use blocks
            for tool in sdk_result.tool_executions:
                assistant_content.append({
                    "type": "tool_use",
                    "id": tool.id,
                    "name": tool.name,
                    "input": tool.input
                })
            
            messages.append({
                "role": "assistant",
                "content": assistant_content
            })
            
            # Add tool results
            tool_results = []
            for tool in sdk_result.tool_executions:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool.id,
                    "content": tool.result,
                    "is_error": tool.is_error
                })
            
            messages.append({
                "role": "user",
                "content": tool_results
            })
        
        return messages
    
    async def _stream_response(
        self,
        prompt: str,
        output_queue: asyncio.Queue,
    ) -> str:
        """Stream a simple response without tool context."""
        full_response = ""
        
        self._history.add_user_message(prompt)
        
        try:
            request_params = {
                "model": self.config.streaming_model,
                "max_tokens": self.config.max_tokens,
                "system": self.config.system_prompt,
                "messages": self._history.to_api_format(),
            }
            
            async with self.client.messages.stream(**request_params) as stream:
                async for event in stream:
                    if self._interrupted:
                        await output_queue.put({"type": "interrupted"})
                        break
                    
                    if isinstance(event, ContentBlockDeltaEvent):
                        if hasattr(event.delta, 'text'):
                            text = event.delta.text
                            full_response += text
                            await output_queue.put({
                                "type": "delta",
                                "content": text
                            })
            
            await output_queue.put({"type": "complete"})
            self._history.add_assistant_message(full_response)
            
            return full_response
            
        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            await output_queue.put({
                "type": "error",
                "error": str(e)
            })
            return full_response
    
    def clear_history(self) -> None:
        """Clear conversation history."""
        self._history.clear()
        if self._orchestrator:
            self._orchestrator.clear_messages()
    
    def get_history(self) -> List[Dict[str, Any]]:
        """Get current conversation history."""
        return self._history.to_api_format()
    
    def interrupt(self) -> None:
        """Interrupt current processing."""
        self._interrupted = True
    
    def reset_interrupt(self) -> None:
        """Reset interrupt flag."""
        self._interrupted = False


# Register with AgentFactory
AgentFactory.register("sdk_hybrid", SDKHybridAgent)
