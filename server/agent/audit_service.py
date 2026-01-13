"""
Legacy compatibility module for audit_service.

Re-exports from audit package for backwards compatibility.

TODO: Update imports to use `from audit import ...` directly.
"""

from audit.service import (
    get_audit_service,
    init_audit_service,
    shutdown_audit_service,
    EventType,
    EventStatus,
    EventCategory,
    DataSanitizer,
    AuditEvent,
)

__all__ = [
    "get_audit_service",
    "init_audit_service",
    "shutdown_audit_service",
    "EventType",
    "EventStatus",
    "EventCategory",
    "DataSanitizer",
    "AuditEvent",
]
