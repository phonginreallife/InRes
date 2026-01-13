"""
Legacy compatibility module for routes_conversations.

Re-exports from routes.conversations for backwards compatibility.

TODO: Update imports to use `from routes import ...` directly.
"""

from routes.conversations import (
    save_conversation,
    save_message,
    update_conversation_activity,
)

__all__ = [
    "save_conversation",
    "save_message",
    "update_conversation_activity",
]
