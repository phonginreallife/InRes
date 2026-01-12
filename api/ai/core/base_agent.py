"""
Base Agent Abstract Class.

Defines the interface that all agent implementations must follow,
ensuring consistent behavior between legacy and streaming modes.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for agent instances."""
    
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    system_prompt: str = """You are an AI assistant specialized in incident response and DevOps.
You help users manage incidents, analyze alerts, and troubleshoot issues.
Be concise but thorough in your responses."""
    tools: List[Dict[str, Any]] = field(default_factory=list)
    
    # Optional features
    enable_thinking: bool = False
    temperature: float = 1.0


class BaseAgent(ABC):
    """
    Abstract base class for AI agents.
    
    Both legacy (Claude SDK) and streaming (direct API) implementations
    inherit from this class to ensure consistent interfaces.
    
    Subclasses must implement:
    - process_message(): Main method to process user input
    - clear_history(): Reset conversation state
    - interrupt(): Stop current processing
    """
    
    def __init__(self, config: AgentConfig = None):
        """
        Initialize the agent with configuration.
        
        Args:
            config: Agent configuration (uses defaults if not provided)
        """
        self.config = config or AgentConfig()
        self._interrupted = False
        self._processing = False
    
    @abstractmethod
    async def process_message(
        self,
        prompt: str,
        output_queue: asyncio.Queue,
        tool_executor: Optional[Callable[[str, Dict], Any]] = None,
    ) -> str:
        """
        Process a user message and stream responses to output queue.
        
        This is the main entry point for agent interactions. Implementations
        should:
        1. Add the user message to conversation history
        2. Send the message to the LLM
        3. Stream responses to output_queue as events
        4. Handle tool calls if tool_executor is provided
        5. Return the complete assistant response text
        
        Args:
            prompt: User's input message
            output_queue: Queue to send streaming events to
            tool_executor: Optional function to execute tools
        
        Returns:
            Complete assistant response text
        
        Events sent to output_queue should follow this format:
            - {"type": "delta", "content": "token"}  # Text tokens
            - {"type": "thinking", "content": "..."}  # Thinking blocks
            - {"type": "tool_use", "id": "...", "name": "...", "input": {...}}
            - {"type": "tool_result", "tool_use_id": "...", "content": "..."}
            - {"type": "complete"}  # End of response
            - {"type": "error", "error": "..."}  # On error
        """
        pass
    
    @abstractmethod
    def clear_history(self) -> None:
        """
        Clear conversation history.
        
        Resets the agent to a fresh state, removing all previous
        messages from the conversation context.
        """
        pass
    
    @abstractmethod
    def get_history(self) -> List[Dict[str, Any]]:
        """
        Get current conversation history.
        
        Returns:
            List of message dictionaries in the conversation
        """
        pass
    
    def interrupt(self) -> None:
        """
        Signal to interrupt current processing.
        
        Sets the interrupt flag that implementations should check
        during streaming to stop gracefully.
        """
        self._interrupted = True
        logger.info("Agent interrupt requested")
    
    def reset_interrupt(self) -> None:
        """Reset interrupt flag for new query."""
        self._interrupted = False
    
    @property
    def is_interrupted(self) -> bool:
        """Check if agent has been interrupted."""
        return self._interrupted
    
    @property
    def is_processing(self) -> bool:
        """Check if agent is currently processing a message."""
        return self._processing
    
    def _set_processing(self, value: bool) -> None:
        """Set processing state (for internal use by implementations)."""
        self._processing = value


class AgentFactory:
    """
    Factory for creating agent instances.
    
    Allows switching between implementations at runtime based on
    configuration or feature flags.
    """
    
    _implementations: Dict[str, type] = {}
    
    @classmethod
    def register(cls, name: str, implementation: type) -> None:
        """
        Register an agent implementation.
        
        Args:
            name: Identifier for the implementation (e.g., "streaming", "legacy")
            implementation: Class that inherits from BaseAgent
        """
        if not issubclass(implementation, BaseAgent):
            raise TypeError(f"{implementation} must inherit from BaseAgent")
        cls._implementations[name] = implementation
        logger.info(f"Registered agent implementation: {name}")
    
    @classmethod
    def create(cls, name: str, config: AgentConfig = None, **kwargs) -> BaseAgent:
        """
        Create an agent instance.
        
        Args:
            name: Name of the registered implementation
            config: Agent configuration
            **kwargs: Additional arguments passed to the implementation
        
        Returns:
            Agent instance
        
        Raises:
            ValueError: If implementation name is not registered
        """
        if name not in cls._implementations:
            available = list(cls._implementations.keys())
            raise ValueError(f"Unknown agent: {name}. Available: {available}")
        
        return cls._implementations[name](config=config, **kwargs)
    
    @classmethod
    def list_implementations(cls) -> List[str]:
        """List all registered implementation names."""
        return list(cls._implementations.keys())
