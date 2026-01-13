# InRes AI Agent

AI-powered incident response assistant built with FastAPI and Claude SDK.

## Overview

The InRes Agent provides an intelligent conversational interface for incident management, leveraging Claude's capabilities with custom tools for incident response workflows.

## Architecture

```
agent/
├── main.py                    # Entry point (uvicorn)
├── claude_agent_api_v1.py     # Legacy block-based agent
├── streaming/                 # Token-level streaming (new)
│   ├── agent.py              # Streaming agent implementation
│   ├── routes.py             # WebSocket endpoints
│   ├── mcp_client.py         # MCP client integration
│   └── mcp_config.py         # MCP configuration
├── routes/                    # REST API endpoints
│   ├── conversations.py      # Chat history
│   ├── audit.py              # Audit logs
│   ├── mcp.py                # MCP management
│   ├── memory.py             # Agent memory
│   └── marketplace.py        # Plugin marketplace
├── tools/                     # Agent tool definitions
│   └── incidents.py          # Incident management tools
├── services/                  # Business logic
├── security/                  # Zero-trust verification
├── audit/                     # Security audit logging
├── config/                    # Configuration loader
├── core/                      # Shared abstractions
└── utils/                     # Utilities
```

## Endpoints

| Endpoint | Type | Description |
|----------|------|-------------|
| `/ws/chat` | WebSocket | Legacy block-based chat |
| `/ws/stream` | WebSocket | Token-level streaming chat |
| `/ws/secure/chat` | WebSocket | Zero-trust secured chat |
| `/api/*` | REST | Various REST endpoints |

## Tech Stack

- **Framework**: FastAPI + Uvicorn
- **AI**: Claude SDK (`claude-agent-sdk`), Anthropic API
- **Protocol**: MCP (Model Context Protocol)
- **Database**: PostgreSQL (via Supabase)
- **Auth**: JWT tokens

## Quick Start

### Local Development

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set config path (shared with Go API)
export inres_CONFIG_PATH=../api/cmd/server/dev.config.yaml

# Run the server
uvicorn main:app --host 0.0.0.0 --port 8002 --reload
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `inres_CONFIG_PATH` | Path to config YAML | - |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `SUPABASE_URL` | Supabase instance URL | - |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service key | - |
| `DATABASE_URL` | PostgreSQL connection string | - |
| `PORT` | Server port | `8002` |
| `USER_WORKSPACES_DIR` | User workspace directory | `/app/workspaces` |

### Docker

```bash
# Build image
docker build -t inres-agent .

# Run container
docker run -p 8002:8002 \
  -e ANTHROPIC_API_KEY=your-key \
  -e inres_CONFIG_PATH=/app/config.yaml \
  -v ./config.yaml:/app/config.yaml \
  inres-agent
```

## Features

- **Incident Tools**: Create, update, and manage incidents via natural language
- **MCP Integration**: Connect to external tools via Model Context Protocol
- **Streaming**: Real-time token-level response streaming
- **Memory**: Persistent conversation memory and context
- **Audit Logging**: Security audit trail for all agent actions
- **Zero-Trust Security**: Device certificate verification
- **Plugin Marketplace**: Extensible plugin system

## Development

### Project Structure

- `streaming/` - New token-level streaming implementation (preferred)
- `claude_agent_api_v1.py` - Legacy block-based implementation (compatibility)

### Adding New Tools

Tools are defined in `tools/` and exposed via MCP:

```python
# tools/incidents.py
@mcp_server.tool()
async def create_incident(title: str, severity: str, ...):
    """Create a new incident."""
    # Implementation
```

### Running Tests

```bash
pytest tests/
```

## Related Services

- **inres-api** (`:8080`) - Go backend API
- **inres-frontend** (`:3000`) - Next.js web UI
- **inres-slack-worker** - Slack integration worker
