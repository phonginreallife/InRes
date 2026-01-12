"""
InRes AI Agent API - Main Entry Point.

This is the main FastAPI application that serves both legacy (block-based)
and streaming (token-level) agent endpoints.

Architecture:
    main.py (this file)
    ├── /ws/chat        → legacy agent (claude_agent_api_v1.py)
    ├── /ws/stream      → streaming agent (streaming/)
    ├── /ws/secure/chat → zero-trust legacy agent
    └── /api/*          → REST endpoints (routes/)

Packages:
    - streaming/    Token-level streaming (new)
    - legacy/       Block-level streaming (compatibility)
    - routes/       HTTP API endpoints
    - services/     Business logic (storage, analytics)
    - audit/        Security audit logging
    - security/     Zero trust verification
    - tools/        Agent tool definitions
    - core/         Shared abstractions
    - config/       Configuration
    - utils/        Utilities

Usage:
    uvicorn main:app --host 0.0.0.0 --port 8002 --reload
"""

# Import the FastAPI app from legacy module
# This maintains backwards compatibility while allowing future migration
from claude_agent_api_v1 import app

# Re-export for uvicorn
__all__ = ["app"]
