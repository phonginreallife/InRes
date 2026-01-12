#!/bin/bash
# =============================================================================
# Stop Cloudflare Tunnels and Clean Up
# =============================================================================

echo "🛑 Stopping Cloudflare tunnels..."
pkill cloudflared 2>/dev/null || echo "No tunnels running"

# Remove .env.local if it exists
ENV_FILE="$(dirname "$0")/../frontend/inres/.env.local"
if [ -f "$ENV_FILE" ]; then
    rm "$ENV_FILE"
    echo "🗑️  Removed $ENV_FILE"
fi

# Clean up temp files
rm -rf /tmp/inres-tunnels 2>/dev/null

echo "  Tunnels stopped and cleaned up"
