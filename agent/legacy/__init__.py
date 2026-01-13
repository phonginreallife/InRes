"""
Legacy Package - Block-based Claude Agent SDK Integration.

This package provides the original agent implementation using the
Claude Agent SDK, which delivers block-based responses.

The main implementation remains in claude_agent_api_v1.py for now.
This package provides a clean import interface.

Features:
- Block-based streaming (complete message blocks)
- Full Claude SDK integration with permissions
- Tool approval workflow (interactive, rule_based, hybrid)
- Complete audit trail for all operations

Usage:
    from legacy import agent_task, agent_task_streaming
    
    # Or access the full app
    from legacy import app
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import main components from legacy module
from claude_agent_api_v1 import (
    app,
    agent_task,
    agent_task_streaming,
    websocket_chat,
    websocket_secure_chat,
    verify_websocket_auth,
)

__all__ = [
    "app",
    "agent_task",
    "agent_task_streaming",
    "websocket_chat",
    "websocket_secure_chat",
    "verify_websocket_auth",
]
