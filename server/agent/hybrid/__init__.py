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

Two Agent Options:
1. SDKHybridAgent (RECOMMENDED): Uses Claude Agent SDK for tools + Direct API for streaming
2. HybridAgent (legacy): Uses direct API for both planning and streaming

Usage:
    # Recommended: SDK-based agent
    from hybrid import SDKHybridAgent, SDKHybridAgentConfig
    
    agent = SDKHybridAgent(config=SDKHybridAgentConfig(...))
    response = await agent.process_message(
        prompt, output_queue,
        auth_token=token, org_id=org_id
    )
    
    # Legacy: Direct API agent
    from hybrid import HybridAgent, HybridAgentConfig
    
    agent = HybridAgent(config=HybridAgentConfig(...))
    response = await agent.process_message(prompt, output_queue, tool_executor)
"""

# SDK-based hybrid agent (RECOMMENDED)
from .sdk_agent import SDKHybridAgent, SDKHybridAgentConfig
from .sdk_orchestrator import (
    SDKOrchestrator,
    SDKOrchestratorResult,
    ActionType as SDKActionType,
    ToolExecution,
)

# Legacy hybrid agent (direct API for everything)
from .agent import HybridAgent, HybridAgentConfig
from .orchestrator import AgentOrchestrator, OrchestratorAction, ActionType

__all__ = [
    # SDK-based Agent (RECOMMENDED)
    "SDKHybridAgent",
    "SDKHybridAgentConfig",
    "SDKOrchestrator",
    "SDKOrchestratorResult",
    "SDKActionType",
    "ToolExecution",
    # Legacy Agent
    "HybridAgent",
    "HybridAgentConfig",
    "AgentOrchestrator",
    "OrchestratorAction",
    "ActionType",
]
