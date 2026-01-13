"""
InRes AI Agent API - Main Entry Point.

This is the main FastAPI application using HybridAgent for
token-level streaming with SDK-style tool orchestration.

Architecture:
    main.py (this file)
    ├── /ws/chat        → HybridAgent (token streaming + tool orchestration)
    ├── /ws/secure/chat → HybridAgent with Zero-Trust auth
    └── /api/*          → REST endpoints (routes/)

Packages:
    - hybrid/       HybridAgent (production agent)
    - streaming/    INCIDENT_TOOLS and MCP client pool
    - routes/       HTTP API endpoints
    - services/     Business logic (storage, analytics)
    - audit/        Security audit logging
    - security/     Zero trust verification
    - tools/        Agent tool definitions
    - core/         Shared abstractions (BaseAgent, ToolExecutor)
    - config/       Configuration
    - utils/        Utilities

Usage:
    uvicorn main:app --host 0.0.0.0 --port 8002 --reload
"""

from claude_agent_api_v1 import app

__all__ = ["app"]
