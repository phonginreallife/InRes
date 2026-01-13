"""
Legacy compatibility module for incident_tools.

Re-exports from tools package for backwards compatibility.

TODO: Update imports to use `from tools import ...` directly.
"""

from tools import (
    create_incident_tools_server,
    set_auth_token,
    set_org_id,
    set_project_id,
)

__all__ = [
    "create_incident_tools_server",
    "set_auth_token",
    "set_org_id",
    "set_project_id",
]
