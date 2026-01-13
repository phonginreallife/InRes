"""
Token-level Streaming Agent using Anthropic API directly.

This module provides true token-by-token streaming from the LLM to the frontend,
while still supporting tool calls.

Architecture:
    LLM (Anthropic) → streaming_agent → WebSocket → Frontend
         ↑                  ↑                ↑
    token deltas      forward deltas    append tokens

Key Features:
- True token streaming (not block streaming)
- Tool support with streaming
- Compatible with existing WebSocket infrastructure
- Integrates with core.ToolExecutor for unified tool handling
- Uses core.MessageHistory patterns for conversation management

Module Organization:
    This module is part of the streaming package. See also:
    - core/base_agent.py: Abstract base class interface
    - core/tool_executor.py: Unified tool execution
    - core/message_history.py: Message validation and repair
    - routes_streaming.py: WebSocket endpoint
    - mcp_streaming_client.py: MCP server integration
"""

import asyncio
import json
import logging
import os
import uuid
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

import anthropic
from anthropic.types import (
    ContentBlockDeltaEvent,
    ContentBlockStartEvent,
    ContentBlockStopEvent,
    Message,
    MessageStartEvent,
    MessageStopEvent,
    TextDelta,
    ToolUseBlock,
)

# Import core abstractions
from core.base_agent import BaseAgent, AgentConfig, AgentFactory
from core.message_history import MessageHistory

logger = logging.getLogger(__name__)

# Default system prompt for incident response
DEFAULT_SYSTEM_PROMPT = """You are an AI assistant specialized in incident response and DevOps. 
You help users manage incidents, analyze alerts, and troubleshoot issues.
Be concise but thorough in your responses."""


class StreamingAgent(BaseAgent):
    """
    Agent that streams tokens from Anthropic API to output queue.
    
    Inherits from BaseAgent to ensure interface compatibility with
    legacy mode and enable runtime switching via AgentFactory.
    
    Supports:
    - Token-by-token text streaming
    - Tool calls with streaming
    - Multi-turn conversations
    - Interruption handling
    - MessageHistory for validated conversation management
    """
    
    def __init__(
        self,
        api_key: str = None,
        model: str = "claude-sonnet-4-20250514",
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        tools: List[Dict[str, Any]] = None,
        max_tokens: int = 4096,
        config: AgentConfig = None,  # For BaseAgent compatibility
    ):
        # Initialize BaseAgent
        if config is None:
            config = AgentConfig(
                model=model,
                max_tokens=max_tokens,
                system_prompt=system_prompt,
                tools=tools or []
            )
        super().__init__(config)
        
        # Streaming-specific initialization
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = config.model
        self.system_prompt = config.system_prompt
        self.tools = config.tools
        self.max_tokens = config.max_tokens
        self.client = anthropic.AsyncAnthropic(api_key=self.api_key)
        
        # Use MessageHistory for validated conversation management
        self._history = MessageHistory()
        
        # Legacy compatibility: expose messages as property
        # This allows existing code to still access self.messages
    
    @property
    def messages(self) -> List[Dict[str, Any]]:
        """Legacy compatibility: access messages as list."""
        return self._history.to_api_format()
    
    @messages.setter
    def messages(self, value: List[Dict[str, Any]]) -> None:
        """Legacy compatibility: set messages from list."""
        self._history = MessageHistory(messages=value)
    
    def add_user_message(self, content: str) -> None:
        """Add a user message to conversation history."""
        self._history.add_user_message(content)
    
    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to conversation history."""
        self._history.add_assistant_message(content)
    
    def add_assistant_with_content(self, content: List[Dict[str, Any]]) -> None:
        """Add assistant message with structured content (text + tool_use blocks)."""
        self._history.add_assistant_with_content(content)
    
    def add_tool_result(self, tool_use_id: str, result: str) -> None:
        """Add a tool result to conversation history.
        
        DEPRECATED: Use add_tool_results() for multiple results.
        This method is kept for backwards compatibility but should be
        used only when there's a single tool result.
        """
        self._history.add_tool_results([{"tool_use_id": tool_use_id, "result": result}])
    
    def add_tool_results(self, results: list) -> None:
        """Add multiple tool results in a single user message.
        
        The Anthropic API requires ALL tool_results for a single assistant
        message to be in ONE user message. This method handles that correctly.
        
        Args:
            results: List of dicts with 'tool_use_id' and 'result' keys
        """
        self._history.add_tool_results(results)
    
    def clear_history(self) -> None:
        """Clear conversation history (implements BaseAgent interface)."""
        self._history.clear()
    
    def get_history(self) -> List[Dict[str, Any]]:
        """Get conversation history (implements BaseAgent interface)."""
        return self._history.to_api_format()
    
    async def process_message(
        self,
        prompt: str,
        output_queue: asyncio.Queue,
        tool_executor: Callable[[str, Dict], Any] = None,
    ) -> str:
        """
        Process a user message (implements BaseAgent interface).
        
        This is an alias for stream_response() to conform to the BaseAgent
        interface, enabling runtime switching between agent implementations.
        
        See stream_response() for full documentation.
        """
        return await self.stream_response(prompt, output_queue, tool_executor)
    
    def validate_and_fix_history(self) -> None:
        """
        Validate conversation history and fix any issues that would cause API errors.
        
        Delegates to MessageHistory.validate_and_repair() which handles:
        - Dangling tool_use blocks without corresponding tool_results
        - Missing tool_results after tool_use
        - Recovery from interrupted/failed tool execution
        """
        repaired = self._history.validate_and_repair()
        if repaired:
            logger.info("Conversation history was fixed to resolve tool_use/tool_result mismatches")
    
    async def stream_response(
        self,
        prompt: str,
        output_queue: asyncio.Queue,
        tool_executor: Callable[[str, Dict], Any] = None,
    ) -> str:
        """
        Stream a response from Claude, forwarding tokens to output_queue.
        
        Args:
            prompt: User's input message
            output_queue: Queue to send streaming events to
            tool_executor: Optional function to execute tools
        
        Returns:
            Complete assistant response text
        
        Events sent to output_queue:
            - {"type": "delta", "content": "token"}  # Each token
            - {"type": "thinking", "content": "..."}  # Thinking (if enabled)
            - {"type": "tool_use", "id": "...", "name": "...", "input": {...}}
            - {"type": "tool_result", "id": "...", "content": "..."}
            - {"type": "complete"}  # End of response
            - {"type": "error", "error": "..."}  # On error
        """
        self.reset_interrupt()
        
        # Validate and fix any corrupted history before adding new message
        self.validate_and_fix_history()
        
        self.add_user_message(prompt)
        
        full_response = ""
        
        try:
            # Build request parameters
            request_params = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "system": self.system_prompt,
                "messages": self.messages,
            }
            
            # Add tools if available
            if self.tools:
                request_params["tools"] = self.tools
            
            # Stream the response
            async with self.client.messages.stream(**request_params) as stream:
                current_tool_use = None
                tool_input_json = ""
                pending_tool_results = []  # Store tool results until we have final_message
                
                async for event in stream:
                    # Check for interruption
                    if self._interrupted:
                        logger.info("Stream interrupted")
                        await output_queue.put({"type": "interrupted"})
                        break
                    
                    # Handle different event types
                    if isinstance(event, ContentBlockStartEvent):
                        content_block = event.content_block
                        if hasattr(content_block, 'type'):
                            if content_block.type == "tool_use":
                                current_tool_use = {
                                    "id": content_block.id,
                                    "name": content_block.name,
                                }
                                tool_input_json = ""
                                logger.debug(f"Tool use started: {content_block.name}")
                    
                    elif isinstance(event, ContentBlockDeltaEvent):
                        delta = event.delta
                        
                        # Text delta - send immediately
                        if hasattr(delta, 'text'):
                            text = delta.text
                            full_response += text
                            await output_queue.put({
                                "type": "delta",
                                "content": text
                            })
                        
                        # Tool input delta - accumulate JSON
                        elif hasattr(delta, 'partial_json'):
                            tool_input_json += delta.partial_json
                    
                    elif isinstance(event, ContentBlockStopEvent):
                        # Tool use complete - execute if we have executor
                        if current_tool_use and tool_input_json:
                            try:
                                tool_input = json.loads(tool_input_json)
                                current_tool_use["input"] = tool_input
                                
                                # Send tool_use event to frontend
                                await output_queue.put({
                                    "type": "tool_use",
                                    "id": current_tool_use["id"],
                                    "name": current_tool_use["name"],
                                    "input": tool_input
                                })
                                
                                # Execute tool if executor provided
                                if tool_executor:
                                    tool_result = await self._execute_tool(
                                        current_tool_use["name"],
                                        tool_input,
                                        tool_executor
                                    )
                                    
                                    # Send tool result to frontend
                                    await output_queue.put({
                                        "type": "tool_result",
                                        "tool_use_id": current_tool_use["id"],
                                        "content": tool_result,
                                        "is_error": False
                                    })
                                    
                                    # Store tool use info for later (after we get final_message)
                                    pending_tool_results.append({
                                        "tool_use_id": current_tool_use["id"],
                                        "result": tool_result
                                    })
                                    
                            except json.JSONDecodeError as e:
                                logger.error(f"Failed to parse tool input: {e}")
                                # Still add error result to prevent history corruption
                                if tool_executor and current_tool_use:
                                    error_result = f"Error: Failed to parse tool input JSON: {str(e)}"
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
                
                # Get final message for history
                final_message = await stream.get_final_message()
                
                # Check if we need to continue (tool use requires another turn)
                if final_message.stop_reason == "tool_use" and tool_executor:
                    # IMPORTANT: Add assistant message with tool_use FIRST
                    # Convert final_message.content to proper format
                    assistant_content = []
                    for block in final_message.content:
                        if hasattr(block, 'text'):
                            assistant_content.append({"type": "text", "text": block.text})
                        elif hasattr(block, 'id'):  # tool_use block
                            assistant_content.append({
                                "type": "tool_use",
                                "id": block.id,
                                "name": block.name,
                                "input": block.input
                            })
                    
                    # Add assistant message with tool_use content using proper method
                    self.add_assistant_with_content(assistant_content)
                    
                    # NOW add tool results (user message) - ALL in ONE message!
                    # The Anthropic API requires all tool_results for one assistant
                    # message to be in a single user message
                    self.add_tool_results(pending_tool_results)
                    
                    # Continue conversation with tool results
                    try:
                        continued_response = await self._continue_after_tools(
                            output_queue, tool_executor
                        )
                        full_response += continued_response
                    except Exception as cont_error:
                        # Continuation failed - add a synthetic response so history stays valid
                        logger.error(f"Continuation failed, adding recovery message: {cont_error}")
                        recovery_msg = f"I encountered an error while processing the tool results. Error: {str(cont_error)}"
                        self.add_assistant_message(recovery_msg)
                        full_response += recovery_msg
                        await output_queue.put({"type": "delta", "content": recovery_msg})
            
            # Add assistant response to history (only if we didn't already add via tool continuation)
            if full_response and (not pending_tool_results or final_message.stop_reason != "tool_use"):
                self.add_assistant_message(full_response)
            
            # Send complete signal
            await output_queue.put({"type": "complete"})
            
            return full_response
            
        except anthropic.APIError as e:
            error_msg = f"Anthropic API error: {str(e)}"
            logger.error(error_msg)
            await output_queue.put({"type": "error", "error": error_msg})
            # CRITICAL: Clear corrupted message history to prevent future API errors
            # This happens when tool_use blocks don't have corresponding tool_result blocks
            if "tool_use" in str(e) and "tool_result" in str(e):
                logger.warning("Detected corrupted message history (tool_use without tool_result), clearing history")
                self.clear_history()
            return ""
        except Exception as e:
            error_msg = f"Streaming error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            await output_queue.put({"type": "error", "error": error_msg})
            # Don't raise - let the session continue with clean state
            return ""
    
    async def _execute_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        executor: Callable
    ) -> str:
        """Execute a tool and return the result."""
        try:
            if asyncio.iscoroutinefunction(executor):
                result = await executor(tool_name, tool_input)
            else:
                result = executor(tool_name, tool_input)
            return str(result) if result is not None else "Tool executed successfully"
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return f"Error executing tool: {str(e)}"
    
    async def _continue_after_tools(
        self,
        output_queue: asyncio.Queue,
        tool_executor: Callable
    ) -> str:
        """Continue streaming after tool execution."""
        # Recursive call to continue the conversation
        # Use empty prompt since we're continuing from tool results
        return await self._stream_continuation(output_queue, tool_executor)
    
    async def _stream_continuation(
        self,
        output_queue: asyncio.Queue,
        tool_executor: Callable
    ) -> str:
        """Stream continuation after tool use."""
        full_response = ""
        
        # Validate history before continuation to catch any issues
        self.validate_and_fix_history()
        
        try:
            request_params = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "system": self.system_prompt,
                "messages": self.messages,
            }
            
            if self.tools:
                request_params["tools"] = self.tools
            
            async with self.client.messages.stream(**request_params) as stream:
                current_tool_use = None
                tool_input_json = ""
                pending_tool_results = []  # Store tool results until we have final_message
                
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
                            await output_queue.put({"type": "delta", "content": text})
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
                                    # Store for later (after we have final_message)
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
                
                # Continue if more tools needed
                if final_message.stop_reason == "tool_use" and tool_executor:
                    # IMPORTANT: Add assistant message with tool_use FIRST
                    assistant_content = []
                    for block in final_message.content:
                        if hasattr(block, 'text'):
                            assistant_content.append({"type": "text", "text": block.text})
                        elif hasattr(block, 'id'):  # tool_use block
                            assistant_content.append({
                                "type": "tool_use",
                                "id": block.id,
                                "name": block.name,
                                "input": block.input
                            })
                    
                    self.add_assistant_with_content(assistant_content)
                    
                    # NOW add tool results (user message) - ALL in ONE message!
                    self.add_tool_results(pending_tool_results)
                    
                    try:
                        continued = await self._stream_continuation(output_queue, tool_executor)
                        full_response += continued
                    except Exception as cont_error:
                        # Add recovery message to keep history valid
                        logger.error(f"Nested continuation failed: {cont_error}")
                        recovery_msg = f"Error processing: {str(cont_error)}"
                        self.add_assistant_message(recovery_msg)
                        full_response += recovery_msg
                        await output_queue.put({"type": "delta", "content": recovery_msg})
            
            return full_response
            
        except Exception as e:
            logger.error(f"Continuation error: {e}", exc_info=True)
            # Add a recovery message to keep conversation valid
            recovery = "I encountered an error. Please try your request again."
            self.add_assistant_message(recovery)
            await output_queue.put({"type": "delta", "content": recovery})
            return recovery


# Pre-defined tools for InRes incident management (NOT for external services)
INCIDENT_TOOLS = [
    {
        "name": "get_incidents",
        "description": "Get a list of incidents from the InRes platform. Use this to browse and search for InRes incidents. Can filter by status, severity, time range.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["triggered", "acknowledged", "resolved"],
                    "description": "Filter by incident status"
                },
                "severity": {
                    "type": "string",
                    "enum": ["critical", "high", "medium", "low"],
                    "description": "Filter by severity"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of incidents to return",
                    "default": 10
                }
            }
        }
    },
    {
        "name": "get_incident_details",
        "description": "Get detailed information about a specific InRes incident by its UUID. Use this tool (NOT external MCP tools) when you have an InRes incident ID like '1393de28-1916-4f9f-bc2f-36e990a21967'. This fetches incident details from the InRes database.",
        "input_schema": {
            "type": "object",
            "properties": {
                "incident_id": {
                    "type": "string",
                    "description": "The InRes incident UUID (e.g., '1393de28-1916-4f9f-bc2f-36e990a21967')"
                }
            },
            "required": ["incident_id"]
        }
    },
    {
        "name": "acknowledge_incident",
        "description": "Acknowledge an InRes incident to indicate someone is working on it. Use the InRes incident UUID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "incident_id": {
                    "type": "string",
                    "description": "The InRes incident UUID to acknowledge"
                },
                "note": {
                    "type": "string",
                    "description": "Optional note about the acknowledgment"
                }
            },
            "required": ["incident_id"]
        }
    },
    {
        "name": "resolve_incident",
        "description": "Resolve an InRes incident to mark it as fixed. Use the InRes incident UUID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "incident_id": {
                    "type": "string",
                    "description": "The InRes incident UUID to resolve"
                },
                "resolution": {
                    "type": "string",
                    "description": "Description of how the incident was resolved"
                }
            },
            "required": ["incident_id"]
        }
    },
    {
        "name": "get_incident_stats",
        "description": "Get statistics about incidents (counts by status, severity trends).",
        "input_schema": {
            "type": "object",
            "properties": {
                "time_range": {
                    "type": "string",
                    "enum": ["1h", "24h", "7d", "30d"],
                    "description": "Time range for statistics",
                    "default": "24h"
                }
            }
        }
    }
]


def create_streaming_agent(
    api_key: str = None,
    include_tools: bool = True
) -> StreamingAgent:
    """
    Factory function to create a StreamingAgent with incident tools.
    
    Args:
        api_key: Anthropic API key (or uses ANTHROPIC_API_KEY env var)
        include_tools: Whether to include incident management tools
    
    Returns:
        Configured StreamingAgent instance
    """
    tools = INCIDENT_TOOLS if include_tools else []
    return StreamingAgent(api_key=api_key, tools=tools)


# Register with AgentFactory for runtime switching
AgentFactory.register("streaming", StreamingAgent)
