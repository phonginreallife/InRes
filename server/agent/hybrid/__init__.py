"""
Hybrid Agent Package.

Combines Claude Agent SDK orchestration with direct Anthropic API
token-level streaming for the best of both worlds.

Architecture:
    ┌─────────────────────────────────────────────────────────────┐
    │   UI (WebSocket)  ◄────  Token Deltas  ────  Direct API     │
    │                                              (streaming)     │
    │                              ▲                               │
    │                              │ orchestrates                  │
    │                              ▼                               │
    │                    Claude Agent SDK                          │
    │                    (planning, tools, MCP, permissions)       │
    └─────────────────────────────────────────────────────────────┘

Usage:
    from hybrid import HybridAgent, HybridAgentConfig
    
    agent = HybridAgent(config=HybridAgentConfig(...))
    response = await agent.process_message(prompt, output_queue, tool_executor)
"""

from .agent import HybridAgent, HybridAgentConfig
from .orchestrator import AgentOrchestrator, OrchestratorAction, ActionType

__all__ = [
    # Agent
    "HybridAgent",
    "HybridAgentConfig",
    # Orchestrator
    "AgentOrchestrator",
    "OrchestratorAction",
    "ActionType",
]
