"""
Legacy compatibility module for database_util.

Re-exports from utils.database for backwards compatibility.

TODO: Update imports to use `from utils import ...` directly.
"""

from utils.database import (
    execute_query,
    get_db_connection,
    ensure_user_exists,
    extract_user_info_from_token,
)

__all__ = [
    "execute_query",
    "get_db_connection",
    "ensure_user_exists",
    "extract_user_info_from_token",
]
