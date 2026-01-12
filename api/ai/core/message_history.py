"""
Shared Message History Management.

Provides a unified interface for managing conversation history
that works with both the Anthropic API format and storage.

Features:
- Message validation and normalization
- Tool use/result pairing validation
- History repair for corrupted states
- Serialization for persistence
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class MessageRole(str, Enum):
    """Valid message roles for conversation history."""
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class ToolUse:
    """Represents a tool use block in assistant message."""
    id: str
    name: str
    input: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "tool_use",
            "id": self.id,
            "name": self.name,
            "input": self.input
        }


@dataclass
class ToolResult:
    """Represents a tool result block in user message."""
    tool_use_id: str
    content: str
    is_error: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "type": "tool_result",
            "tool_use_id": self.tool_use_id,
            "content": self.content
        }
        if self.is_error:
            result["is_error"] = True
        return result


@dataclass
class Message:
    """
    A message in the conversation history.
    
    Can contain either:
    - Simple text content (string)
    - Structured content (list of blocks for tool use/results)
    """
    role: MessageRole
    content: Any  # str or List[Dict]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role.value,
            "content": self.content
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        return cls(
            role=MessageRole(data["role"]),
            content=data["content"]
        )
    
    def has_tool_use(self) -> bool:
        """Check if this message contains tool_use blocks."""
        if not isinstance(self.content, list):
            return False
        return any(
            isinstance(block, dict) and block.get("type") == "tool_use"
            for block in self.content
        )
    
    def get_tool_use_ids(self) -> Set[str]:
        """Get all tool_use IDs in this message."""
        if not isinstance(self.content, list):
            return set()
        return {
            block.get("id")
            for block in self.content
            if isinstance(block, dict) and block.get("type") == "tool_use"
        }
    
    def has_tool_results(self) -> bool:
        """Check if this message contains tool_result blocks."""
        if not isinstance(self.content, list):
            return False
        return any(
            isinstance(block, dict) and block.get("type") == "tool_result"
            for block in self.content
        )
    
    def get_tool_result_ids(self) -> Set[str]:
        """Get all tool_use_ids referenced by tool_results in this message."""
        if not isinstance(self.content, list):
            return set()
        return {
            block.get("tool_use_id")
            for block in self.content
            if isinstance(block, dict) and block.get("type") == "tool_result"
        }


class MessageHistory:
    """
    Manages conversation history with validation and repair.
    
    Ensures the history always satisfies Anthropic API requirements:
    - Alternating user/assistant messages
    - Every tool_use has a corresponding tool_result immediately after
    - All tool_results for one assistant message are in one user message
    
    Usage:
        history = MessageHistory()
        history.add_user_message("Hello")
        history.add_assistant_message("Hi there!")
        history.add_tool_use_message([...])
        history.add_tool_results([...])
        
        messages = history.to_api_format()
    """
    
    def __init__(self, messages: List[Dict[str, Any]] = None):
        """
        Initialize message history.
        
        Args:
            messages: Optional list of existing messages to load
        """
        self._messages: List[Message] = []
        
        if messages:
            for msg in messages:
                self._messages.append(Message.from_dict(msg))
    
    def add_user_message(self, content: str) -> None:
        """Add a simple user text message."""
        self._messages.append(Message(
            role=MessageRole.USER,
            content=content
        ))
    
    def add_assistant_message(self, content: str) -> None:
        """Add a simple assistant text message."""
        self._messages.append(Message(
            role=MessageRole.ASSISTANT,
            content=content
        ))
    
    def add_assistant_with_content(self, content: List[Dict[str, Any]]) -> None:
        """
        Add an assistant message with structured content.
        
        Use this when the assistant message contains tool_use blocks
        alongside text blocks.
        
        Args:
            content: List of content blocks (text, tool_use, etc.)
        """
        self._messages.append(Message(
            role=MessageRole.ASSISTANT,
            content=content
        ))
    
    def add_tool_results(self, results: List[Dict[str, Any]]) -> None:
        """
        Add tool results as a user message.
        
        IMPORTANT: All tool results for a single assistant message
        must be added in ONE call to this method. The Anthropic API
        requires all tool_results to be in a single user message.
        
        Args:
            results: List of tool results, each with:
                - tool_use_id: ID of the tool_use this is a response to
                - result: The tool execution result (string)
        """
        if not results:
            return
        
        content = []
        for tr in results:
            content.append({
                "type": "tool_result",
                "tool_use_id": tr["tool_use_id"],
                "content": tr.get("result", tr.get("content", ""))
            })
        
        self._messages.append(Message(
            role=MessageRole.USER,
            content=content
        ))
    
    def clear(self) -> None:
        """Clear all messages from history."""
        self._messages = []
    
    def to_api_format(self) -> List[Dict[str, Any]]:
        """
        Convert to Anthropic API message format.
        
        Returns:
            List of message dicts ready for API call
        """
        return [msg.to_dict() for msg in self._messages]
    
    def to_json(self) -> str:
        """Serialize history to JSON string."""
        return json.dumps(self.to_api_format())
    
    @classmethod
    def from_json(cls, json_str: str) -> "MessageHistory":
        """Deserialize history from JSON string."""
        messages = json.loads(json_str)
        return cls(messages=messages)
    
    def __len__(self) -> int:
        return len(self._messages)
    
    def __iter__(self):
        return iter(self._messages)
    
    def validate_and_repair(self) -> bool:
        """
        Validate history and repair any issues.
        
        Fixes common issues:
        - Missing tool_results after tool_use
        - Multiple separate tool_result messages that should be combined
        
        Returns:
            True if repairs were made, False if history was valid
        """
        if len(self._messages) < 2:
            return False
        
        repaired = False
        i = 0
        
        while i < len(self._messages):
            msg = self._messages[i]
            
            # Check assistant messages with tool_use
            if msg.role == MessageRole.ASSISTANT and msg.has_tool_use():
                tool_use_ids = msg.get_tool_use_ids()
                
                if i + 1 >= len(self._messages):
                    # No next message - add synthetic results
                    logger.warning("Dangling tool_use at end of history, adding synthetic results")
                    self._add_synthetic_results(tool_use_ids)
                    repaired = True
                    break
                
                next_msg = self._messages[i + 1]
                
                if next_msg.role != MessageRole.USER:
                    # Wrong role - need to insert tool_results
                    logger.warning("Missing tool_result after tool_use, inserting synthetic results")
                    self._insert_synthetic_results(i + 1, tool_use_ids)
                    repaired = True
                    i += 1  # Skip inserted message
                else:
                    # Check if all tool_use_ids have results
                    result_ids = next_msg.get_tool_result_ids()
                    missing_ids = tool_use_ids - result_ids
                    
                    if missing_ids:
                        logger.warning(f"Missing tool_results for IDs: {missing_ids}")
                        self._add_missing_results(i + 1, missing_ids)
                        repaired = True
            
            i += 1
        
        return repaired
    
    def _add_synthetic_results(self, tool_use_ids: Set[str]) -> None:
        """Add synthetic tool results at end of history."""
        content = [
            {
                "type": "tool_result",
                "tool_use_id": tid,
                "content": "Tool execution was interrupted. Please try again."
            }
            for tid in tool_use_ids
        ]
        self._messages.append(Message(role=MessageRole.USER, content=content))
    
    def _insert_synthetic_results(self, index: int, tool_use_ids: Set[str]) -> None:
        """Insert synthetic tool results at given index."""
        content = [
            {
                "type": "tool_result",
                "tool_use_id": tid,
                "content": "Tool execution was interrupted. Please try again."
            }
            for tid in tool_use_ids
        ]
        self._messages.insert(index, Message(role=MessageRole.USER, content=content))
    
    def _add_missing_results(self, index: int, missing_ids: Set[str]) -> None:
        """Add missing tool results to existing user message."""
        msg = self._messages[index]
        if isinstance(msg.content, list):
            for tid in missing_ids:
                msg.content.append({
                    "type": "tool_result",
                    "tool_use_id": tid,
                    "content": "Tool result was lost. Please try again."
                })
