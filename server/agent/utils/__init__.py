"""
Utils Package - Utility Functions.

- database: Database query utilities
- git: Git operations for marketplace
- redis_client: Redis-backed state for horizontal scaling
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from .database import execute_query, ensure_user_exists, extract_user_info_from_token
from .git import (
    clone_repository,
    fetch_and_reset,
    get_current_commit,
    ensure_repository,
    get_marketplace_dir,
    build_github_url,
    remove_repository,
    GitError,
)
from .redis_client import (
    get_redis,
    close_redis,
    RateLimiter,
    SessionStore,
    get_rate_limiter,
    get_session_store,
)

__all__ = [
    # Database
    "execute_query",
    "ensure_user_exists", 
    "extract_user_info_from_token",
    # Git
    "clone_repository",
    "fetch_and_reset",
    "get_current_commit",
    "ensure_repository",
    "get_marketplace_dir",
    "build_github_url",
    "remove_repository",
    "GitError",
    # Redis utilities
    "get_redis",
    "close_redis",
    "RateLimiter",
    "SessionStore",
    "get_rate_limiter",
    "get_session_store",
]
