#!/bin/bash
API_URL="http://localhost:8080"
INTEGRATION_ID="${1:-your-integration-id}"

echo "🚀 Sending test PagerDuty webhook..."
curl -s -X POST "http://localhost:8080/webhook/pagerduty/7bba276b-1932-4ee5-ad22-6a7b9902dcd3" \
  -H "Content-Type: application/json" \
  -d '{
    "event": {
      "id": "evt-appsec-002",
      "event_type": "incident.resolved",
      "occurred_at": "2026-01-09T14:40:00Z",
      "agent": {
        "id": "PUSER002",
        "type": "user_reference",
        "name": "Security Team Lead",
        "email": "lead@appsec.io"
      },
      "data": {
        "id": "PINC-APPSEC-001",
        "type": "incident",
        "html_url": "https://appsec.pagerduty.com/incidents/PINC-APPSEC-001",
        "number": 42,
        "status": "resolved",
        "incident_key": "mdaas/security-alert",
        "created_at": "2026-01-09T14:35:00Z",
        "title": "🔒 MDaaS Security Alert - Suspicious Activity Detected",
        "urgency": "high",
        "service": {
          "id": "PSVC-MDAAS",
          "name": "MDaaS Production"
        },
        "resolve_reason": "Confirmed false positive - IP belongs to authorized penetration testing team"
      }
    }
  }' 
echo ""
echo "✅ Done! Check the frontend for the new incident."