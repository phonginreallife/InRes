"""
Legacy compatibility module for supabase_storage.

This module re-exports functions from services.storage for backwards
compatibility with existing imports.

TODO: Update all imports to use `from services import ...` directly.
"""

from services.storage import (
    # Auth & user functions
    extract_user_id_from_token,
    get_user_id_from_token,
    # Supabase client
    get_supabase_client,
    ensure_user_bucket_exists,
    # Workspace
    get_user_workspace_path,
    ensure_user_workspace,
    # Config
    save_config_to_file,
    load_config_from_file,
    # MCP
    get_user_mcp_servers,
    sync_mcp_config_to_local,
    parse_mcp_servers,
    # Skills & plugins
    sync_user_skills,
    load_user_plugins,
    unzip_installed_plugins,
    list_skill_files,
    download_skill_file,
    ensure_claude_skills_dir,
    extract_skill_file,
    # Memory
    sync_memory_to_workspace,
    # Tools
    get_user_allowed_tools,
    add_user_allowed_tool,
    delete_user_allowed_tool,
)

__all__ = [
    # Auth & user functions
    "extract_user_id_from_token",
    "get_user_id_from_token",
    # Supabase client
    "get_supabase_client",
    "ensure_user_bucket_exists",
    # Workspace
    "get_user_workspace_path",
    "ensure_user_workspace",
    # Config
    "save_config_to_file",
    "load_config_from_file",
    # MCP
    "get_user_mcp_servers",
    "sync_mcp_config_to_local",
    "parse_mcp_servers",
    # Skills & plugins
    "sync_user_skills",
    "load_user_plugins",
    "unzip_installed_plugins",
    "list_skill_files",
    "download_skill_file",
    "ensure_claude_skills_dir",
    "extract_skill_file",
    # Memory
    "sync_memory_to_workspace",
    # Tools
    "get_user_allowed_tools",
    "add_user_allowed_tool",
    "delete_user_allowed_tool",
]
