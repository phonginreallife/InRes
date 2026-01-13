"""
Audit Package - Security Audit Logging.

This package provides audit logging for security and compliance:
- service: Main audit service with event logging
- hooks: Hooks for integrating audit with agent tool execution

Usage:
    from audit import get_audit_service, init_audit_service, EventType
    
    # Initialize
    await init_audit_service()
    
    # Get service
    audit = get_audit_service()
    
    # Log events
    await audit.log_session_created(user_id, session_id, ...)
    await audit.log_tool_requested(user_id, session_id, tool_name, ...)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from .service import (
    get_audit_service,
    init_audit_service,
    shutdown_audit_service,
    EventType,
    EventStatus,
)

from .hooks import build_hooks_config

__all__ = [
    # Service
    "get_audit_service",
    "init_audit_service",
    "shutdown_audit_service",
    "EventType",
    "EventStatus",
    # Hooks
    "build_hooks_config",
]
