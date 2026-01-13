"""
Services Package - Business Logic and External Integrations.

This package contains service modules for business logic:
- storage: Supabase storage operations (users, MCP config, plugins)
- analytics: Incident analytics and PGMQ consumer

Usage:
    from services import storage, analytics
    
    # Storage operations
    user_id = storage.extract_user_id_from_token(token)
    mcp_servers = await storage.get_user_mcp_servers(token, user_id)
    
    # Analytics
    await analytics.start_pgmq_consumer()
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from .storage import (
    extract_user_id_from_token,
    get_user_mcp_servers,
    get_user_workspace_path,
    sync_mcp_config_to_local,
    sync_memory_to_workspace,
    sync_user_skills,
    load_user_plugins,
    unzip_installed_plugins,
    get_user_allowed_tools,
    add_user_allowed_tool,
    delete_user_allowed_tool,
)

from .analytics import (
    start_pgmq_consumer,
    stop_pgmq_consumer,
)

__all__ = [
    # Storage
    "extract_user_id_from_token",
    "get_user_mcp_servers",
    "get_user_workspace_path",
    "sync_mcp_config_to_local",
    "sync_memory_to_workspace",
    "sync_user_skills",
    "load_user_plugins",
    "unzip_installed_plugins",
    "get_user_allowed_tools",
    "add_user_allowed_tool",
    "delete_user_allowed_tool",
    # Analytics
    "start_pgmq_consumer",
    "stop_pgmq_consumer",
]
