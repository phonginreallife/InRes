"""
Legacy compatibility module for git_utils.

Re-exports from utils.git for backwards compatibility.

TODO: Update imports to use `from utils import ...` directly.
"""

from utils.git import (
    clone_repository,
    fetch_and_reset,
    get_current_commit,
    get_remote_commit,
    ensure_repository,
    is_git_repository,
    remove_repository,
    build_github_url,
    get_marketplace_dir,
    run_git_command,
    GitError,
)

__all__ = [
    "clone_repository",
    "fetch_and_reset",
    "get_current_commit",
    "get_remote_commit",
    "ensure_repository",
    "is_git_repository",
    "remove_repository",
    "build_github_url",
    "get_marketplace_dir",
    "run_git_command",
    "GitError",
]
