#!/bin/bash
# Test full PagerDuty webhook flow: TRIGGER -> wait -> RESOLVE
# Usage: ./test-webhook-full-flow.sh [integration_id] [wait_seconds]

INTEGRATION_ID="${1:-91e3593a-58d2-4277-b1c7-6738dac61184}"
WAIT_SECONDS="${2:-5}"
# Use SERVER_URL env var or default to production (no trailing slash!)
API_URL="${SERVER_URL:-https://<domain-name>}"

# Generate unique incident key for this test
INCIDENT_KEY="test/full-flow-$(date +%s)"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

echo "=========================================="
echo " PagerDuty Webhook Full Flow Test"
echo "=========================================="
echo "  API URL: $API_URL"
echo "  Integration ID: $INTEGRATION_ID"
echo "  Incident Key: $INCIDENT_KEY"
echo ""

# Step 1: Trigger incident
echo "[1/3] Sending TRIGGERED event..."
TRIGGER_RESPONSE=$(curl -s -X POST "${API_URL}/api/webhook/pagerduty/${INTEGRATION_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "event": {
      "id": "evt-trigger-'$(date +%s)'",
      "event_type": "incident.triggered",
      "occurred_at": "'"$TIMESTAMP"'",
      "agent": {
        "id": "PUSER001",
        "type": "user_reference",
        "name": "Test User",
        "email": "test@example.com"
      },
      "data": {
        "id": "PINC-FLOW-'$(date +%s)'",
        "type": "incident",
        "html_url": "https://example.pagerduty.com/incidents/PINC-FLOW",
        "number": 100,
        "status": "triggered",
        "incident_key": "'"$INCIDENT_KEY"'",
        "created_at": "'"$TIMESTAMP"'",
        "title": "Full Flow Test - High CPU Usage",
        "description": "CPU usage exceeded 95% on prod-web-01 for more than 5 minutes. The application may become unresponsive. Check the process list and consider scaling up or restarting the service. Related metrics: CPU: 97.3%, Memory: 82.1%, Load Average: 4.2",
        "urgency": "high",
        "service": {
          "id": "PSVC-TEST",
          "name": "Test Service"
        }
      }
    }
  }')
echo "  Response: $TRIGGER_RESPONSE"
echo ""

# Step 2: Wait
echo "[2/3] Waiting ${WAIT_SECONDS} seconds before resolving..."
echo "      (Check the frontend - incident should be visible now)"
sleep "$WAIT_SECONDS"
echo ""

# Step 3: Resolve incident
echo "[3/3] Sending RESOLVED event..."
RESOLVE_RESPONSE=$(curl -s -X POST "${API_URL}/api/webhook/pagerduty/${INTEGRATION_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "event": {
      "id": "evt-resolved-'$(date +%s)'",
      "event_type": "incident.resolved",
      "occurred_at": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
      "agent": {
        "id": "PUSER001",
        "type": "user_reference",
        "name": "Test User",
        "email": "test@example.com"
      },
      "data": {
        "id": "PINC-FLOW-RESOLVED",
        "type": "incident",
        "html_url": "https://example.pagerduty.com/incidents/PINC-FLOW",
        "number": 100,
        "status": "resolved",
        "incident_key": "'"$INCIDENT_KEY"'",
        "created_at": "'"$TIMESTAMP"'",
        "title": "Full Flow Test - High CPU Usage",
        "description": "CPU usage returned to normal levels (45%). Issue was caused by a runaway process.",
        "urgency": "high",
        "resolve_reason": {
          "type": "user_action",
          "incident": {
            "id": "PINC-FLOW",
            "type": "incident_reference"
          }
        },
        "service": {
          "id": "PSVC-TEST",
          "name": "Test Service"
        }
      }
    }
  }')
echo "  Response: $RESOLVE_RESPONSE"
echo ""

echo "=========================================="
echo " Test Complete!"
echo "=========================================="
echo "Check the frontend:"
echo "  - Incident should now be RESOLVED"
echo "  - Check incident timeline for resolution note"
echo ""
