"""
Legacy Module - Claude SDK Block-based Responses.

This module provides the original agent implementation using the
Claude Agent SDK, which delivers block-based responses.

Components:
- Agent task functions from claude_agent_api_v1.py
- Full permission handling and hooks
- Comprehensive audit integration

Features:
- Block-based streaming (complete message blocks)
- Full Claude SDK integration with permissions
- Tool approval workflow (interactive, rule_based, hybrid)
- Complete audit trail for all operations

Note:
    This module is maintained for backwards compatibility and as a
    fallback option. New features should be developed in the streaming
    module where possible.

Usage:
    The legacy agent is accessed via the /ws/chat WebSocket endpoint
    defined in claude_agent_api_v1.py.
"""

__all__ = [
    "agent_task",
    "agent_task_streaming",
]

# Lazy imports from the main module
def __getattr__(name):
    if name in ("agent_task", "agent_task_streaming"):
        from claude_agent_api_v1 import agent_task, agent_task_streaming
        return locals()[name]
    
    raise AttributeError(f"module 'legacy' has no attribute '{name}'")
