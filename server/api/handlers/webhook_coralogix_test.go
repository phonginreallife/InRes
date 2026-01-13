package handlers

import (
	"encoding/json"
	"testing"
	"time"
)

func TestProcessCoralogixWebhook(t *testing.T) {
	handler := &WebhookHandler{}

	tests := []struct {
		name          string
		payload       string
		expectedAlert ProcessedAlert
		checkFields   []string
	}{
		{
			name: "Critical Alert Triggered",
			payload: `{
				"uuid": "abc123-def456",
				"alert_id": "alert-001",
				"alert_name": "High Error Rate",
				"alert_url": "https://coralogix.com/alerts/alert-001",
				"alert_severity": "Critical",
				"alert_type": "logs",
				"alert_action": "trigger",
				"application": "production-api",
				"subsystem": "payment-service",
				"computer": "srv-prod-01",
				"ip_address": "10.0.1.100",
				"timestamp": "2024-01-15T10:30:00Z",
				"hit_count": 150,
				"log_text": "Error: Payment processing failed",
				"duration": "5m",
				"team_name": "Platform Team",
				"description": "Error rate exceeded 5% threshold"
			}`,
			expectedAlert: ProcessedAlert{
				AlertName:   "High Error Rate",
				Severity:    "critical",
				Status:      "firing",
				Summary:     "High Error Rate",
				Description: "Error rate exceeded 5% threshold",
				Fingerprint: "alert-001",
			},
			checkFields: []string{"AlertName", "Severity", "Status", "Summary", "Description", "Fingerprint"},
		},
		{
			name: "Warning Alert Triggered",
			payload: `{
				"uuid": "ghi789-jkl012",
				"alert_id": "alert-002",
				"alert_name": "High Latency Warning",
				"alert_url": "https://coralogix.com/alerts/alert-002",
				"alert_severity": "Warning",
				"alert_type": "metrics",
				"alert_action": "trigger",
				"application": "production-api",
				"subsystem": "user-service",
				"computer": "srv-prod-02",
				"ip_address": "10.0.1.101",
				"timestamp": "2024-01-15T11:00:00Z",
				"hit_count": 50,
				"duration": "10m",
				"team_name": "Platform Team",
				"description": "P95 latency above 500ms"
			}`,
			expectedAlert: ProcessedAlert{
				AlertName:   "High Latency Warning",
				Severity:    "warning",
				Status:      "firing",
				Summary:     "High Latency Warning",
				Description: "P95 latency above 500ms",
				Fingerprint: "alert-002",
			},
			checkFields: []string{"AlertName", "Severity", "Status", "Description", "Fingerprint"},
		},
		{
			name: "Error Alert Triggered",
			payload: `{
				"uuid": "mno345-pqr678",
				"alert_id": "alert-003",
				"alert_name": "Database Connection Error",
				"alert_url": "https://coralogix.com/alerts/alert-003",
				"alert_severity": "Error",
				"alert_type": "logs",
				"alert_action": "trigger",
				"application": "production-api",
				"subsystem": "database",
				"computer": "db-prod-01",
				"ip_address": "10.0.2.50",
				"timestamp": "2024-01-15T12:00:00Z",
				"hit_count": 25,
				"log_text": "Connection refused to primary database",
				"duration": "2m",
				"team_name": "DBA Team"
			}`,
			expectedAlert: ProcessedAlert{
				AlertName:   "Database Connection Error",
				Severity:    "high",
				Status:      "firing",
				Summary:     "Database Connection Error",
				Description: "Connection refused to primary database",
				Fingerprint: "alert-003",
			},
			checkFields: []string{"AlertName", "Severity", "Status", "Description", "Fingerprint"},
		},
		{
			name: "Info Alert Triggered",
			payload: `{
				"uuid": "stu901-vwx234",
				"alert_id": "alert-004",
				"alert_name": "Deployment Completed",
				"alert_url": "https://coralogix.com/alerts/alert-004",
				"alert_severity": "Info",
				"alert_type": "logs",
				"alert_action": "trigger",
				"application": "production-api",
				"subsystem": "deployment",
				"computer": "ci-server",
				"ip_address": "10.0.3.10",
				"timestamp": "2024-01-15T13:00:00Z",
				"hit_count": 1,
				"log_text": "Deployment v2.5.0 completed successfully",
				"duration": "0m",
				"team_name": "DevOps Team",
				"description": "New version deployed to production"
			}`,
			expectedAlert: ProcessedAlert{
				AlertName:   "Deployment Completed",
				Severity:    "info",
				Status:      "firing",
				Summary:     "Deployment Completed",
				Description: "New version deployed to production",
				Fingerprint: "alert-004",
			},
			checkFields: []string{"AlertName", "Severity", "Status", "Description", "Fingerprint"},
		},
		{
			name: "Alert Resolved",
			payload: `{
				"uuid": "yza567-bcd890",
				"alert_id": "alert-001",
				"alert_name": "High Error Rate",
				"alert_url": "https://coralogix.com/alerts/alert-001",
				"alert_severity": "Critical",
				"alert_type": "logs",
				"alert_action": "resolve",
				"application": "production-api",
				"subsystem": "payment-service",
				"computer": "srv-prod-01",
				"ip_address": "10.0.1.100",
				"timestamp": "2024-01-15T11:00:00Z",
				"hit_count": 0,
				"duration": "30m",
				"team_name": "Platform Team",
				"description": "Error rate back to normal"
			}`,
			expectedAlert: ProcessedAlert{
				AlertName:   "High Error Rate",
				Severity:    "critical",
				Status:      "resolved",
				Summary:     "High Error Rate",
				Description: "Error rate back to normal",
				Fingerprint: "alert-001",
			},
			checkFields: []string{"AlertName", "Status", "Description", "Fingerprint"},
		},
		{
			name: "Alert with Meta Labels",
			payload: `{
				"uuid": "efg123-hij456",
				"alert_id": "alert-005",
				"alert_name": "Pod Restart Alert",
				"alert_url": "https://coralogix.com/alerts/alert-005",
				"alert_severity": "Warning",
				"alert_type": "logs",
				"alert_action": "trigger",
				"application": "k8s-cluster",
				"subsystem": "api-deployment",
				"computer": "node-01",
				"ip_address": "10.0.4.20",
				"timestamp": "2024-01-15T14:00:00Z",
				"hit_count": 5,
				"log_text": "Pod restarted due to OOMKilled",
				"duration": "1h",
				"team_name": "K8s Team",
				"meta_labels": {
					"environment": "production",
					"cluster": "us-west-2",
					"namespace": "default"
				}
			}`,
			expectedAlert: ProcessedAlert{
				AlertName:   "Pod Restart Alert",
				Severity:    "warning",
				Status:      "firing",
				Summary:     "Pod Restart Alert",
				Description: "Pod restarted due to OOMKilled",
				Fingerprint: "alert-005",
			},
			checkFields: []string{"AlertName", "Severity", "Status", "Description", "Fingerprint"},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var payload map[string]interface{}
			if err := json.Unmarshal([]byte(tt.payload), &payload); err != nil {
				t.Fatalf("Failed to unmarshal payload: %v", err)
			}

			alerts := handler.processCoralogixWebhook(payload)

			if len(alerts) != 1 {
				t.Fatalf("Expected 1 alert, got %d", len(alerts))
			}

			alert := alerts[0]

			// Check specified fields
			for _, field := range tt.checkFields {
				switch field {
				case "AlertName":
					if alert.AlertName != tt.expectedAlert.AlertName {
						t.Errorf("AlertName = %v, want %v", alert.AlertName, tt.expectedAlert.AlertName)
					}
				case "Severity":
					if alert.Severity != tt.expectedAlert.Severity {
						t.Errorf("Severity = %v, want %v", alert.Severity, tt.expectedAlert.Severity)
					}
				case "Status":
					if alert.Status != tt.expectedAlert.Status {
						t.Errorf("Status = %v, want %v", alert.Status, tt.expectedAlert.Status)
					}
				case "Summary":
					if alert.Summary != tt.expectedAlert.Summary {
						t.Errorf("Summary = %v, want %v", alert.Summary, tt.expectedAlert.Summary)
					}
				case "Description":
					if alert.Description != tt.expectedAlert.Description {
						t.Errorf("Description = %v, want %v", alert.Description, tt.expectedAlert.Description)
					}
				case "Fingerprint":
					if alert.Fingerprint != tt.expectedAlert.Fingerprint {
						t.Errorf("Fingerprint = %v, want %v", alert.Fingerprint, tt.expectedAlert.Fingerprint)
					}
				}
			}

			// Check Labels
			if alert.Labels["source"] != "coralogix" {
				t.Errorf("Labels[source] = %v, want coralogix", alert.Labels["source"])
			}

			// Check timestamp
			if alert.StartsAt.IsZero() {
				t.Error("StartsAt should not be zero")
			}
		})
	}
}

func TestMapCoralogixSeverity(t *testing.T) {
	tests := []struct {
		name     string
		severity string
		expected string
	}{
		{
			name:     "Critical maps to critical",
			severity: "Critical",
			expected: "critical",
		},
		{
			name:     "Error maps to high",
			severity: "Error",
			expected: "high",
		},
		{
			name:     "Warning maps to warning",
			severity: "Warning",
			expected: "warning",
		},
		{
			name:     "Info maps to info",
			severity: "Info",
			expected: "info",
		},
		{
			name:     "Lowercase critical maps to critical",
			severity: "critical",
			expected: "critical",
		},
		{
			name:     "Empty severity defaults to warning",
			severity: "",
			expected: "warning",
		},
		{
			name:     "Unknown severity defaults to warning",
			severity: "Unknown",
			expected: "warning",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := mapCoralogixSeverity(tt.severity)
			if result != tt.expected {
				t.Errorf("mapCoralogixSeverity(%s) = %v, want %v", tt.severity, result, tt.expected)
			}
		})
	}
}

func TestCoralogixWebhookToProcessedAlert(t *testing.T) {
	timestamp, _ := time.Parse(time.RFC3339, "2024-01-15T10:30:00Z")

	webhook := CoralogixWebhook{
		UUID:          "abc123-def456",
		AlertID:       "alert-001",
		AlertName:     "High Error Rate",
		AlertURL:      "https://coralogix.com/alerts/alert-001",
		AlertSeverity: "Critical",
		AlertType:     "logs",
		AlertAction:   "trigger",
		Application:   "production-api",
		Subsystem:     "payment-service",
		Computer:      "srv-prod-01",
		IPAddress:     "10.0.1.100",
		Timestamp:     "2024-01-15T10:30:00Z",
		HitCount:      150,
		LogText:       "Error: Payment processing failed",
		Duration:      "5m",
		TeamName:      "Platform Team",
		Description:   "Error rate exceeded 5% threshold",
		MetaLabels: map[string]string{
			"environment": "production",
			"region":      "us-west-2",
		},
	}

	alert := webhook.ToProcessedAlert()

	// Check basic fields
	if alert.AlertName != "High Error Rate" {
		t.Errorf("AlertName = %v, want High Error Rate", alert.AlertName)
	}
	if alert.Severity != "critical" {
		t.Errorf("Severity = %v, want critical", alert.Severity)
	}
	if alert.Status != "firing" {
		t.Errorf("Status = %v, want firing", alert.Status)
	}
	if alert.Fingerprint != "alert-001" {
		t.Errorf("Fingerprint = %v, want alert-001", alert.Fingerprint)
	}
	if alert.Description != "Error rate exceeded 5% threshold" {
		t.Errorf("Description = %v, want Error rate exceeded 5%% threshold", alert.Description)
	}

	// Check labels
	if alert.Labels["source"] != "coralogix" {
		t.Errorf("Labels[source] = %v, want coralogix", alert.Labels["source"])
	}
	if alert.Labels["application"] != "production-api" {
		t.Errorf("Labels[application] = %v, want production-api", alert.Labels["application"])
	}
	if alert.Labels["subsystem"] != "payment-service" {
		t.Errorf("Labels[subsystem] = %v, want payment-service", alert.Labels["subsystem"])
	}
	if alert.Labels["computer"] != "srv-prod-01" {
		t.Errorf("Labels[computer] = %v, want srv-prod-01", alert.Labels["computer"])
	}
	if alert.Labels["hit_count"] != 150 {
		t.Errorf("Labels[hit_count] = %v, want 150", alert.Labels["hit_count"])
	}
	if alert.Labels["team_name"] != "Platform Team" {
		t.Errorf("Labels[team_name] = %v, want Platform Team", alert.Labels["team_name"])
	}

	// Check meta labels
	if alert.Labels["meta_environment"] != "production" {
		t.Errorf("Labels[meta_environment] = %v, want production", alert.Labels["meta_environment"])
	}
	if alert.Labels["meta_region"] != "us-west-2" {
		t.Errorf("Labels[meta_region] = %v, want us-west-2", alert.Labels["meta_region"])
	}

	// Check annotations
	if alert.Annotations["alert_url"] != "https://coralogix.com/alerts/alert-001" {
		t.Errorf("Annotations[alert_url] = %v, want https://coralogix.com/alerts/alert-001", alert.Annotations["alert_url"])
	}
	if alert.Annotations["duration"] != "5m" {
		t.Errorf("Annotations[duration] = %v, want 5m", alert.Annotations["duration"])
	}
	if alert.Annotations["uuid"] != "abc123-def456" {
		t.Errorf("Annotations[uuid] = %v, want abc123-def456", alert.Annotations["uuid"])
	}

	// Check timestamp
	if !alert.StartsAt.Equal(timestamp) {
		t.Errorf("StartsAt = %v, want %v", alert.StartsAt, timestamp)
	}
}

func TestCoralogixWebhookDescriptionFallback(t *testing.T) {
	// Test that log_text is used when description is empty
	webhook := CoralogixWebhook{
		AlertID:       "alert-001",
		AlertName:     "Test Alert",
		AlertSeverity: "Warning",
		AlertAction:   "trigger",
		LogText:       "This is the log text",
		Description:   "",
	}

	alert := webhook.ToProcessedAlert()

	if alert.Description != "This is the log text" {
		t.Errorf("Description = %v, want This is the log text", alert.Description)
	}
}

func TestCoralogixWebhookResolveAction(t *testing.T) {
	webhook := CoralogixWebhook{
		AlertID:       "alert-001",
		AlertName:     "Test Alert",
		AlertSeverity: "Critical",
		AlertAction:   "resolve",
	}

	alert := webhook.ToProcessedAlert()

	if alert.Status != "resolved" {
		t.Errorf("Status = %v, want resolved", alert.Status)
	}
}

func TestCoralogixWebhookLegacyProcessing(t *testing.T) {
	handler := &WebhookHandler{}

	// Test legacy format (simple structure)
	payload := map[string]interface{}{
		"alert_id":       "legacy-001",
		"alert_name":     "Legacy Alert",
		"alert_severity": "Error",
		"alert_action":   "trigger",
		"application":    "legacy-app",
		"subsystem":      "legacy-sub",
		"description":    "Legacy alert description",
		"alert_url":      "https://coralogix.com/alerts/legacy-001",
	}

	alerts := handler.processCoralogixWebhook(payload)

	if len(alerts) != 1 {
		t.Fatalf("Expected 1 alert, got %d", len(alerts))
	}

	alert := alerts[0]
	if alert.AlertName != "Legacy Alert" {
		t.Errorf("AlertName = %v, want Legacy Alert", alert.AlertName)
	}
	if alert.Severity != "high" {
		t.Errorf("Severity = %v, want high", alert.Severity)
	}
	if alert.Status != "firing" {
		t.Errorf("Status = %v, want firing", alert.Status)
	}
	if alert.Fingerprint != "legacy-001" {
		t.Errorf("Fingerprint = %v, want legacy-001", alert.Fingerprint)
	}
}

func TestCoralogixTimestampParsing(t *testing.T) {
	tests := []struct {
		name      string
		timestamp string
		expectNow bool
	}{
		{
			name:      "Valid RFC3339 timestamp",
			timestamp: "2024-01-15T10:30:00Z",
			expectNow: false,
		},
		{
			name:      "Empty timestamp falls back to now",
			timestamp: "",
			expectNow: true,
		},
		{
			name:      "Invalid timestamp falls back to now",
			timestamp: "not-a-timestamp",
			expectNow: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			webhook := CoralogixWebhook{
				AlertID:       "test-001",
				AlertName:     "Test Alert",
				AlertSeverity: "Warning",
				AlertAction:   "trigger",
				Timestamp:     tt.timestamp,
			}

			before := time.Now()
			alert := webhook.ToProcessedAlert()
			after := time.Now()

			if tt.expectNow {
				// Should be approximately now
				if alert.StartsAt.Before(before) || alert.StartsAt.After(after) {
					t.Errorf("StartsAt = %v, expected to be between %v and %v", alert.StartsAt, before, after)
				}
			} else {
				// Should be the parsed time
				expected, _ := time.Parse(time.RFC3339, tt.timestamp)
				if !alert.StartsAt.Equal(expected) {
					t.Errorf("StartsAt = %v, want %v", alert.StartsAt, expected)
				}
			}
		})
	}
}
