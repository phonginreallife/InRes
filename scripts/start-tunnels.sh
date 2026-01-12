#!/bin/bash
# =============================================================================
# Cloudflare Tunnel Script for Testing Webhooks
# =============================================================================
# Use this script to expose your local inres app to the internet for testing
# webhooks from external services like PagerDuty, Coralogix, etc.
#
# Usage: ./scripts/start-tunnels.sh
# Stop:  pkill cloudflared
# =============================================================================

set -e

# Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo "Installing cloudflared..."
    mkdir -p ~/.local/bin
    curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o ~/.local/bin/cloudflared
    chmod +x ~/.local/bin/cloudflared
    export PATH="$HOME/.local/bin:$PATH"
fi

# Configuration
API_PORT=${API_PORT:-8080}
FRONTEND_PORT=${FRONTEND_PORT:-3000}
SUPABASE_PORT=${SUPABASE_PORT:-54321}
SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY:-"sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH"}

# Temporary files to store URLs
TUNNEL_DIR="/tmp/inres-tunnels"
mkdir -p "$TUNNEL_DIR"

echo "🚀 Starting Cloudflare Tunnels..."
echo ""

# Start API tunnel
cloudflared tunnel --url http://localhost:$API_PORT 2>&1 | tee "$TUNNEL_DIR/api.log" &
API_PID=$!

# Start Frontend tunnel
cloudflared tunnel --url http://localhost:$FRONTEND_PORT 2>&1 | tee "$TUNNEL_DIR/frontend.log" &
FRONTEND_PID=$!

# Start Supabase tunnel
cloudflared tunnel --url http://localhost:$SUPABASE_PORT 2>&1 | tee "$TUNNEL_DIR/supabase.log" &
SUPABASE_PID=$!

# Wait for tunnels to be ready
echo "⏳ Waiting for tunnels to initialize..."
sleep 8

# Extract URLs
API_URL=$(grep -o 'https://[^|]*trycloudflare.com' "$TUNNEL_DIR/api.log" | head -1 | tr -d ' ')
FRONTEND_URL=$(grep -o 'https://[^|]*trycloudflare.com' "$TUNNEL_DIR/frontend.log" | head -1 | tr -d ' ')
SUPABASE_URL=$(grep -o 'https://[^|]*trycloudflare.com' "$TUNNEL_DIR/supabase.log" | head -1 | tr -d ' ')

echo ""
echo "=============================================="
echo "  Tunnels are ready!"
echo "=============================================="
echo ""
echo "📱 Frontend:  $FRONTEND_URL"
echo "🔌 API:       $API_URL"
echo "🗄️  Supabase:  $SUPABASE_URL"
echo ""
echo "=============================================="
echo "Webhook URLs:"
echo "=============================================="
echo ""
echo "PagerDuty:  $API_URL/webhook/pagerduty/{integration_id}"
echo "Coralogix:  $API_URL/webhook/coralogix/{integration_id}"
echo "Prometheus: $API_URL/webhook/prometheus/{integration_id}"
echo "Datadog:    $API_URL/webhook/datadog/{integration_id}"
echo "Grafana:    $API_URL/webhook/grafana/{integration_id}"
echo ""

# Create .env.local for frontend
ENV_FILE="$(dirname "$0")/../frontend/inres/.env.local"
cat > "$ENV_FILE" << EOF
NEXT_PUBLIC_API_URL=$API_URL
NEXT_PUBLIC_AI_API_URL=$API_URL
NEXT_PUBLIC_SUPABASE_URL=$SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY=$SUPABASE_ANON_KEY
EOF

echo "📝 Created $ENV_FILE"
echo ""
echo "⚠️  Restart your frontend to pick up the new config:"
echo "    cd frontend/inres && npm run dev"
echo ""
echo "🛑 To stop tunnels: pkill cloudflared"
echo ""

# Keep script running
wait
