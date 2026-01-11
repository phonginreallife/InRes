#!/bin/bash
# Test PagerDuty webhook - sends a TRIGGERED event to create a new incident
# Usage: ./test-webhook.sh [integration_id]

INTEGRATION_ID="${1:-d907ccc4-a415-4f9b-ba94-881e3f760901}"
# Use SERVER_URL env var or default to localhost
API_URL="${SERVER_URL:-http://localhost:8080}"

echo "🚀 Sending test PagerDuty webhook (TRIGGERED event)..."
curl -s -X POST "${API_URL}/webhook/pagerduty/${INTEGRATION_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "event": {
      "id": "evt-test-'$(date +%s)'",
      "event_type": "incident.triggered",
      "occurred_at": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
      "agent": {
        "id": "PUSER001",
        "type": "user_reference",
        "name": "Test User",
        "email": "test@example.com"
      },
      "data": {
        "id": "PINC-TEST-'$(date +%s)'",
        "type": "incident",
        "html_url": "https://example.pagerduty.com/incidents/PINC-TEST",
        "number": 99,
        "status": "triggered",
        "incident_key": "test/alert-'$(date +%s)'",
        "created_at": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
        "title": "🔥 Test Alert - High CPU Usage Detected",
        "urgency": "high",
        "service": {
          "id": "PSVC-TEST",
          "name": "Test Service"
        }
      }
    }
  }' 
echo ""
echo "✅ Done! Check the frontend for the new incident."