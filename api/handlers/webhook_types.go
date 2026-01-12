package handlers

import (
	"fmt"
	"strconv"
	"strings"
	"time"
)

// Prometheus AlertManager webhook payload
// Reference: https://prometheus.io/docs/alerting/latest/configuration/#webhook_config
type PrometheusWebhook struct {
	Version           string            `json:"version"`
	GroupKey          string            `json:"groupKey"`
	TruncatedAlerts   int               `json:"truncatedAlerts"`
	Status            string            `json:"status"`
	Receiver          string            `json:"receiver"`
	GroupLabels       map[string]string `json:"groupLabels"`
	CommonLabels      map[string]string `json:"commonLabels"`
	CommonAnnotations map[string]string `json:"commonAnnotations"`
	ExternalURL       string            `json:"externalURL"`
	Alerts            []PrometheusAlert `json:"alerts"`
}

type PrometheusAlert struct {
	Status       string            `json:"status"` // firing, resolved
	Labels       map[string]string `json:"labels"`
	Annotations  map[string]string `json:"annotations"`
	StartsAt     time.Time         `json:"startsAt"`
	EndsAt       time.Time         `json:"endsAt"`
	GeneratorURL string            `json:"generatorURL"`
	Fingerprint  string            `json:"fingerprint"`
}

// Datadog webhook payload
// Reference: https://docs.datadoghq.com/integrations/webhooks/
type DatadogWebhook struct {
	ID            string     `json:"id"`
	Title         string     `json:"title"`
	Body          string     `json:"body"`
	EventType     string     `json:"event_type"`
	AlertType     string     `json:"alert_type"`
	AlertPriority string     `json:"alert_priority"` // P1, P2, P3, P4
	Transition    string     `json:"transition"`     // Triggered, Recovered
	Date          string     `json:"date"`           // Unix timestamp in milliseconds (as string)
	LastUpdated   string     `json:"last_updated"`   // Unix timestamp in milliseconds (as string)
	Org           DatadogOrg `json:"org"`
	Tags          string     `json:"tags"`
	Snapshot      string     `json:"snapshot"`
	Link          string     `json:"link"`
	// Additional fields that might be present
	Metadata      map[string]interface{} `json:"metadata,omitempty"`
	Aggregate     string                 `json:"aggregate"`
	AlertTitle    string                 `json:"alert_title"`
	AlertStatus   string                 `json:"alert_status"`
	AlertQuery    string                 `json:"alert_query"`
	AlertCycleKey string                 `json:"alert_cycle_key"`
}

type DatadogOrg struct {
	ID   string `json:"id"`
	Name string `json:"name"`
}

// Grafana webhook payload
// Reference: https://grafana.com/docs/grafana/latest/alerting/configure-notifications/manage-contact-points/integrations/webhook-notifier/
type GrafanaWebhook struct {
	Receiver          string            `json:"receiver"`
	Status            string            `json:"status"`
	Alerts            []GrafanaAlert    `json:"alerts"`
	GroupLabels       map[string]string `json:"groupLabels"`
	CommonLabels      map[string]string `json:"commonLabels"`
	CommonAnnotations map[string]string `json:"commonAnnotations"`
	ExternalURL       string            `json:"externalURL"`
	Version           string            `json:"version"`
	GroupKey          string            `json:"groupKey"`
	TruncatedAlerts   int               `json:"truncatedAlerts"`
	OrgID             int64             `json:"orgId"`
	Title             string            `json:"title"`
	State             string            `json:"state"` // alerting, ok, pending
	Message           string            `json:"message"`
	RuleName          string            `json:"ruleName"`
	RuleURL           string            `json:"ruleUrl"`
	DashboardID       int64             `json:"dashboardId"`
	PanelID           int64             `json:"panelId"`
	ImageURL          string            `json:"imageUrl"`
}

type GrafanaAlert struct {
	Status       string             `json:"status"`
	Labels       map[string]string  `json:"labels"`
	Annotations  map[string]string  `json:"annotations"`
	StartsAt     time.Time          `json:"startsAt"`
	EndsAt       time.Time          `json:"endsAt"`
	GeneratorURL string             `json:"generatorURL"`
	Fingerprint  string             `json:"fingerprint"`
	SilenceURL   string             `json:"silenceURL"`
	DashboardURL string             `json:"dashboardURL"`
	PanelURL     string             `json:"panelURL"`
	Values       map[string]float64 `json:"values"`
}

// AWS CloudWatch webhook payload (via SNS)
// Reference: https://docs.aws.amazon.com/sns/latest/dg/sns-message-and-json-formats.html
type AWSWebhook struct {
	Type             string `json:"Type"` // Notification, SubscriptionConfirmation
	MessageId        string `json:"MessageId"`
	TopicArn         string `json:"TopicArn"`
	Subject          string `json:"Subject"`
	Message          string `json:"Message"` // JSON string containing CloudWatch alarm
	Timestamp        string `json:"Timestamp"`
	SignatureVersion string `json:"SignatureVersion"`
	Signature        string `json:"Signature"`
	SigningCertURL   string `json:"SigningCertURL"`
	UnsubscribeURL   string `json:"UnsubscribeURL"`
}

// AWS CloudWatch Alarm (nested in SNS Message)
type AWSCloudWatchAlarm struct {
	AlarmName        string               `json:"AlarmName"`
	AlarmDescription string               `json:"AlarmDescription"`
	AWSAccountId     string               `json:"AWSAccountId"`
	NewStateValue    string               `json:"NewStateValue"` // ALARM, OK, INSUFFICIENT_DATA
	NewStateReason   string               `json:"NewStateReason"`
	StateChangeTime  string               `json:"StateChangeTime"`
	Region           string               `json:"Region"`
	AlarmArn         string               `json:"AlarmArn"`
	OldStateValue    string               `json:"OldStateValue"`
	Trigger          AWSCloudWatchTrigger `json:"Trigger"`
}

type AWSCloudWatchTrigger struct {
	MetricName                       string                   `json:"MetricName"`
	Namespace                        string                   `json:"Namespace"`
	StatisticType                    string                   `json:"StatisticType"`
	Statistic                        string                   `json:"Statistic"`
	Unit                             string                   `json:"Unit"`
	Dimensions                       []AWSCloudWatchDimension `json:"Dimensions"`
	Period                           int                      `json:"Period"`
	EvaluationPeriods                int                      `json:"EvaluationPeriods"`
	ComparisonOperator               string                   `json:"ComparisonOperator"`
	Threshold                        float64                  `json:"Threshold"`
	TreatMissingData                 string                   `json:"TreatMissingData"`
	EvaluateLowSampleCountPercentile string                   `json:"EvaluateLowSampleCountPercentile"`
}

type AWSCloudWatchDimension struct {
	Name  string `json:"name"`
	Value string `json:"value"`
}

// PagerDuty webhook payload
// Reference: https://developer.pagerduty.com/docs/webhooks/v3-overview/
type PagerDutyWebhook struct {
	Event PagerDutyEvent `json:"event"`
}

type PagerDutyEvent struct {
	ID           string                `json:"id"`
	EventType    string                `json:"event_type"` // incident.triggered, incident.acknowledged, incident.resolved, etc.
	ResourceType string                `json:"resource_type"`
	OccurredAt   time.Time             `json:"occurred_at"`
	Agent        PagerDutyAgent        `json:"agent"`
	Client       PagerDutyClient       `json:"client"`
	Data         PagerDutyIncidentData `json:"data"`
}

type PagerDutyAgent struct {
	ID    string `json:"id"`
	Type  string `json:"type"` // user_reference, service_reference
	Self  string `json:"self"`
	Name  string `json:"name"`
	Email string `json:"email"`
}

type PagerDutyClient struct {
	Name string `json:"name"`
}

type PagerDutyIncidentData struct {
	ID               string                    `json:"id"`
	Type             string                    `json:"type"`
	Self             string                    `json:"self"`
	HTMLUrl          string                    `json:"html_url"`
	Number           int                       `json:"number"`
	Status           string                    `json:"status"` // triggered, acknowledged, resolved
	IncidentKey      string                    `json:"incident_key"`
	CreatedAt        time.Time                 `json:"created_at"`
	Title            string                    `json:"title"`
	Service          PagerDutyService          `json:"service"`
	Assignees        []PagerDutyAssignee       `json:"assignees"`
	EscalationPolicy PagerDutyEscalationPolicy `json:"escalation_policy"`
	Priority         *PagerDutyPriority        `json:"priority"`
	Urgency          string                    `json:"urgency"` // high, low
	Description      string                    `json:"description"`
	ResolveReason    string                    `json:"resolve_reason"`
	CustomDetails    map[string]interface{}    `json:"custom_details"` // Custom fields from PagerDuty alerts
}

type PagerDutyService struct {
	ID      string `json:"id"`
	Type    string `json:"type"`
	Self    string `json:"self"`
	HTMLUrl string `json:"html_url"`
	Name    string `json:"name"`
}

type PagerDutyAssignee struct {
	ID    string `json:"id"`
	Type  string `json:"type"`
	Self  string `json:"self"`
	Name  string `json:"name"`
	Email string `json:"email"`
}

type PagerDutyEscalationPolicy struct {
	ID      string `json:"id"`
	Type    string `json:"type"`
	Self    string `json:"self"`
	HTMLUrl string `json:"html_url"`
	Name    string `json:"name"`
}

type PagerDutyPriority struct {
	ID    string `json:"id"`
	Type  string `json:"type"`
	Self  string `json:"self"`
	Name  string `json:"name"` // P1, P2, P3, P4, P5
	Color string `json:"color"`
}

// Coralogix webhook payload
// Reference: https://coralogix.com/docs/webhooks/
type CoralogixWebhook struct {
	UUID          string                 `json:"uuid"`
	AlertID       string                 `json:"alert_id"`
	AlertName     string                 `json:"alert_name"`
	AlertURL      string                 `json:"alert_url"`
	AlertSeverity string                 `json:"alert_severity"` // Info, Warning, Error, Critical
	AlertType     string                 `json:"alert_type"`
	AlertAction   string                 `json:"alert_action"` // trigger, resolve
	Application   string                 `json:"application"`
	Subsystem     string                 `json:"subsystem"`
	Computer      string                 `json:"computer"`
	IPAddress     string                 `json:"ip_address"`
	Timestamp     string                 `json:"timestamp"`
	HitCount      int                    `json:"hit_count"`
	QueryResult   []CoralogixQueryResult `json:"query_result"`
	MetaLabels    map[string]string      `json:"meta_labels"`
	LogText       string                 `json:"log_text"`
	Duration      string                 `json:"duration"`
	TeamName      string                 `json:"team_name"`
	Description   string                 `json:"description"`
}

type CoralogixQueryResult struct {
	Timestamp   string                 `json:"timestamp"`
	Severity    string                 `json:"severity"`
	Text        string                 `json:"text"`
	Application string                 `json:"application"`
	Subsystem   string                 `json:"subsystem"`
	Computer    string                 `json:"computer"`
	IPAddress   string                 `json:"ip_address"`
	Metadata    map[string]interface{} `json:"metadata"`
}

// Generic webhook payload (for custom integrations)
type GenericWebhook struct {
	AlertName   string                 `json:"alert_name"`
	Severity    string                 `json:"severity"`
	Status      string                 `json:"status"`
	Summary     string                 `json:"summary"`
	Description string                 `json:"description"`
	Labels      map[string]interface{} `json:"labels"`
	Annotations map[string]interface{} `json:"annotations"`
	StartsAt    *time.Time             `json:"starts_at,omitempty"`
	EndsAt      *time.Time             `json:"ends_at,omitempty"`
	Fingerprint string                 `json:"fingerprint,omitempty"`
}

// Helper functions to convert webhook structs to ProcessedAlert

func (p *PrometheusAlert) ToProcessedAlert() ProcessedAlert {
	alert := ProcessedAlert{
		AlertName:   p.Labels["alertname"],
		Severity:    p.Labels["severity"],
		Status:      p.Status,
		Summary:     p.Annotations["summary"],
		Description: p.Annotations["description"],
		Labels:      convertStringMapToInterface(p.Labels),
		Annotations: convertStringMapToInterface(p.Annotations),
		StartsAt:    p.StartsAt,
		Fingerprint: p.Fingerprint,
	}

	// Set default severity if not provided
	if alert.Severity == "" {
		alert.Severity = "warning"
	}

	// Set default alert name if not provided
	if alert.AlertName == "" {
		alert.AlertName = "unknown"
	}

	if !p.EndsAt.IsZero() {
		alert.EndsAt = &p.EndsAt
	}

	return alert
}

func (d *DatadogWebhook) ToProcessedAlert() ProcessedAlert {
	// Determine severity based on alert_priority (P1, P2, P3, P4)
	var severity string
	transitionLower := strings.ToLower(d.Transition)

	if strings.Contains(transitionLower, "recovered") {
		severity = "info"
	} else {
		severity = mapDatadogPriority(d.AlertPriority)
	}

	alert := ProcessedAlert{
		AlertName:   d.Title,
		Severity:    severity,
		Status:      mapDatadogStatus(d.Transition),
		Summary:     d.Title, // Summary is the body content
		Description: d.Body,  // Description is the title
		Priority:    d.AlertPriority,
		Fingerprint: d.Aggregate,
		Labels: map[string]interface{}{
			"source":          "datadog",
			"event_id":        d.ID,
			"event_type":      d.EventType,
			"alert_priority":  d.AlertPriority,
			"aggregate":       d.Aggregate,
			"alert_query":     d.AlertQuery,
			"alert_cycle_key": d.AlertCycleKey,
			"alert_title":     d.AlertTitle,
			"alert_status":    d.AlertStatus,
			"transition":      d.Transition,
		},
		Annotations: map[string]interface{}{
			"org_id":       d.Org.ID,
			"org_name":     d.Org.Name,
			"last_updated": d.LastUpdated,
			"link":         d.Link,
		},
		StartsAt: parseDatadogTimestampFromString(d.Date, d.LastUpdated),
	}

	// Add tags to labels
	if len(d.Tags) > 0 {
		alert.Labels["tags"] = d.Tags
	}

	return alert
}

// Helper function to parse Datadog timestamp from string
func parseDatadogTimestampFromString(date, lastUpdated string) time.Time {
	// Try to parse date first
	timestampStr := date
	if timestampStr == "" {
		timestampStr = lastUpdated
	}

	if timestampStr != "" {
		// Datadog sends timestamp in milliseconds as string
		if timestampMs, err := strconv.ParseInt(timestampStr, 10, 64); err == nil {
			return time.Unix(0, timestampMs*int64(time.Millisecond))
		}
	}

	// Fallback to current time if parsing fails
	return time.Now()
}

func (g *GrafanaWebhook) ToProcessedAlert() ProcessedAlert {
	alert := ProcessedAlert{
		AlertName:   g.RuleName,
		Severity:    mapGrafanaSeverity(g.State),
		Status:      mapGrafanaStatus(g.State),
		Summary:     g.Message,
		Description: g.Title,
		Labels: map[string]interface{}{
			"source":    "grafana",
			"dashboard": g.DashboardID,
			"panel":     g.PanelID,
		},
		Annotations: map[string]interface{}{
			"grafana_url": g.RuleURL,
			"image_url":   g.ImageURL,
		},
		StartsAt: time.Now(),
	}

	// Add common labels
	for k, v := range g.CommonLabels {
		alert.Labels[k] = v
	}

	// Add common annotations
	for k, v := range g.CommonAnnotations {
		alert.Annotations[k] = v
	}

	return alert
}

func (a *AWSCloudWatchAlarm) ToProcessedAlert() ProcessedAlert {
	alert := ProcessedAlert{
		AlertName:   a.AlarmName,
		Severity:    mapAWSSeverity(a.NewStateValue),
		Status:      mapAWSStatus(a.NewStateValue),
		Summary:     a.AlarmDescription,
		Description: a.NewStateReason,
		Labels: map[string]interface{}{
			"source":    "aws",
			"region":    a.Region,
			"namespace": a.Trigger.Namespace,
		},
		Annotations: map[string]interface{}{
			"account_id": a.AWSAccountId,
			"timestamp":  a.StateChangeTime,
			"alarm_arn":  a.AlarmArn,
		},
		StartsAt: time.Now(),
	}

	// Add dimensions to labels
	for _, dim := range a.Trigger.Dimensions {
		alert.Labels[dim.Name] = dim.Value
	}

	return alert
}

func (g *GenericWebhook) ToProcessedAlert() ProcessedAlert {
	alert := ProcessedAlert{
		AlertName:   g.AlertName,
		Severity:    g.Severity,
		Status:      g.Status,
		Summary:     g.Summary,
		Description: g.Description,
		Labels:      g.Labels,
		Annotations: g.Annotations,
		Fingerprint: g.Fingerprint,
	}

	// Set defaults
	if alert.AlertName == "" {
		alert.AlertName = "generic-alert"
	}
	if alert.Severity == "" {
		alert.Severity = "warning"
	}
	if alert.Status == "" {
		alert.Status = "firing"
	}

	// Map severity to priority
	alert.Priority = mapSeverityToPriority(alert.Severity)

	// Set timestamps
	if g.StartsAt != nil {
		alert.StartsAt = *g.StartsAt
	} else {
		alert.StartsAt = time.Now()
	}

	if g.EndsAt != nil {
		alert.EndsAt = g.EndsAt
	}

	return alert
}

func (p *PagerDutyWebhook) ToProcessedAlert() ProcessedAlert {
	data := p.Event.Data

	// Map PagerDuty status to our status
	// Check both event_type (e.g., "incident.resolved") and data.status
	status := "firing"
	eventType := strings.ToLower(p.Event.EventType)
	dataStatus := strings.ToLower(data.Status)

	// event_type takes precedence (incident.resolved, incident.triggered, etc.)
	if strings.Contains(eventType, "resolved") || dataStatus == "resolved" {
		status = "resolved"
	} else if strings.Contains(eventType, "triggered") || dataStatus == "triggered" {
		status = "firing"
	} else if strings.Contains(eventType, "acknowledged") || dataStatus == "acknowledged" {
		status = "firing" // Still active, just acknowledged
	}

	// Map urgency/priority to severity
	var severity string
	if data.Priority != nil {
		severity = mapPagerDutyPriority(data.Priority.Name)
	} else {
		severity = mapPagerDutyUrgency(data.Urgency)
	}

	// Generate robust fingerprint - use incident_key, fall back to incident_id
	fingerprint := data.IncidentKey
	if fingerprint == "" {
		fingerprint = data.ID
	}

	// Build full description including custom details
	description := data.Description
	if len(data.CustomDetails) > 0 {
		var customDetailsText strings.Builder
		if description != "" {
			customDetailsText.WriteString(description)
			customDetailsText.WriteString("\n\n---\n**Custom Details:**\n")
		}
		for key, value := range data.CustomDetails {
			customDetailsText.WriteString(fmt.Sprintf("- **%s**: %v\n", key, value))
		}
		description = customDetailsText.String()
	}

	alert := ProcessedAlert{
		AlertName:   data.Title,
		Severity:    severity,
		Status:      status,
		Summary:     data.Title,
		Description: description,
		Fingerprint: fingerprint,
		Priority:    getPagerDutyPriorityString(data.Priority),
		Labels: map[string]interface{}{
			"source":          "pagerduty",
			"incident_id":     data.ID,
			"incident_number": data.Number,
			"incident_key":    data.IncidentKey,
			"service_id":      data.Service.ID,
			"service_name":    data.Service.Name,
			"urgency":         data.Urgency,
			"event_type":      p.Event.EventType,
		},
		Annotations: map[string]interface{}{
			"html_url":          data.HTMLUrl,
			"service_url":       data.Service.HTMLUrl,
			"escalation_policy": data.EscalationPolicy.Name,
			"resolve_reason":    data.ResolveReason,
		},
		StartsAt: data.CreatedAt,
	}

	// Add custom details to annotations for structured access
	if len(data.CustomDetails) > 0 {
		alert.Annotations["custom_details"] = data.CustomDetails
	}

	// Add assignees to labels
	if len(data.Assignees) > 0 {
		assigneeNames := make([]string, len(data.Assignees))
		for i, assignee := range data.Assignees {
			assigneeNames[i] = assignee.Name
		}
		alert.Labels["assignees"] = strings.Join(assigneeNames, ", ")
	}

	// Add agent info if available
	if p.Event.Agent.Name != "" {
		alert.Labels["agent_name"] = p.Event.Agent.Name
		alert.Labels["agent_email"] = p.Event.Agent.Email
	}

	return alert
}

func (c *CoralogixWebhook) ToProcessedAlert() ProcessedAlert {
	// Map Coralogix action to status
	// Coralogix sends: "trigger" for firing, "resolve" or "resolved" for resolved
	status := "firing"
	action := strings.ToLower(c.AlertAction)
	if action == "resolve" || action == "resolved" || action == "recovery" || action == "ok" {
		status = "resolved"
	}

	// Map Coralogix severity
	severity := mapCoralogixSeverity(c.AlertSeverity)

	// Parse timestamp
	startsAt := time.Now()
	if c.Timestamp != "" {
		if t, err := time.Parse(time.RFC3339, c.Timestamp); err == nil {
			startsAt = t
		}
	}

	// Build description
	description := c.Description
	if description == "" && c.LogText != "" {
		description = c.LogText
	}

	// Generate a robust fingerprint for deduplication
	// Use alert_id if available, otherwise combine alert_name + application + subsystem
	fingerprint := c.AlertID
	if fingerprint == "" {
		fingerprint = fmt.Sprintf("coralogix-%s-%s-%s", c.AlertName, c.Application, c.Subsystem)
	}

	alert := ProcessedAlert{
		AlertName:   c.AlertName,
		Severity:    severity,
		Status:      status,
		Summary:     c.AlertName,
		Description: description,
		Fingerprint: fingerprint,
		Priority:    mapSeverityToPriority(severity),
		Labels: map[string]interface{}{
			"source":      "coralogix",
			"alert_id":    c.AlertID,
			"alert_type":  c.AlertType,
			"application": c.Application,
			"subsystem":   c.Subsystem,
			"computer":    c.Computer,
			"ip_address":  c.IPAddress,
			"hit_count":   c.HitCount,
			"team_name":   c.TeamName,
		},
		Annotations: map[string]interface{}{
			"alert_url": c.AlertURL,
			"duration":  c.Duration,
			"uuid":      c.UUID,
		},
		StartsAt: startsAt,
	}

	// Add meta labels
	for k, v := range c.MetaLabels {
		alert.Labels["meta_"+k] = v
	}

	return alert
}

// Helper functions for PagerDuty
func mapPagerDutyPriority(priority string) string {
	switch strings.ToUpper(priority) {
	case "P1":
		return "critical"
	case "P2":
		return "high"
	case "P3":
		return "warning"
	case "P4":
		return "low"
	case "P5":
		return "info"
	default:
		return "warning"
	}
}

func mapPagerDutyUrgency(urgency string) string {
	switch strings.ToLower(urgency) {
	case "high":
		return "high"
	case "low":
		return "low"
	default:
		return "warning"
	}
}

func getPagerDutyPriorityString(priority *PagerDutyPriority) string {
	if priority != nil && priority.Name != "" {
		return priority.Name
	}
	return "P3"
}

// Helper functions for Coralogix
func mapCoralogixSeverity(severity string) string {
	switch strings.ToLower(severity) {
	case "critical":
		return "critical"
	case "error":
		return "high"
	case "warning":
		return "warning"
	case "info":
		return "info"
	default:
		return "warning"
	}
}

// Helper function to convert map[string]string to map[string]interface{}
func convertStringMapToInterface(m map[string]string) map[string]interface{} {
	result := make(map[string]interface{})
	for k, v := range m {
		result[k] = v
	}
	return result
}
