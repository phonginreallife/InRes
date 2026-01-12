"""
Core module for shared AI agent abstractions.

This module provides:
- BaseAgent: Abstract base class for all agent implementations
- ToolExecutor: Unified tool execution (HTTP + MCP)
- MessageHistory: Shared conversation history management

Both legacy (Claude SDK) and streaming (direct Anthropic API) modes
use these shared abstractions for consistency and code reuse.
"""

from .base_agent import BaseAgent, AgentConfig
from .tool_executor import ToolExecutor, ToolResult
from .message_history import MessageHistory, MessageRole

__all__ = [
    "BaseAgent",
    "AgentConfig", 
    "ToolExecutor",
    "ToolResult",
    "MessageHistory",
    "MessageRole",
]
