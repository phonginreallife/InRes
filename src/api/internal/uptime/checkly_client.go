package uptime

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

const (
	ChecklyAPIURL = "https://api.checklyhq.com/v1"
)

// ChecklyClient handles communication with Checkly API
type ChecklyClient struct {
	apiKey     string
	accountID  string
	httpClient *http.Client
}

// NewChecklyClient creates a new Checkly API client
func NewChecklyClient(apiKey, accountID string) *ChecklyClient {
	return &ChecklyClient{
		apiKey:    apiKey,
		accountID: accountID,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// ChecklyCheck represents a check from Checkly
type ChecklyCheck struct {
	ID                   string   `json:"id"`
	Name                 string   `json:"name"`
	CheckType            string   `json:"checkType"` // API, BROWSER
	Activated            bool     `json:"activated"`
	Muted                bool     `json:"muted"`
	ShouldFail           bool     `json:"shouldFail"`
	Frequency            int      `json:"frequency"` // in minutes
	FrequencyOffset      int      `json:"frequencyOffset"`
	Locations            []string `json:"locations"`
	DegradedResponseTime int      `json:"degradedResponseTime"`
	MaxResponseTime      int      `json:"maxResponseTime"`
	CreatedAt            string   `json:"created_at"`
	UpdatedAt            string   `json:"updated_at"`

	// API Check specific fields
	Request *ChecklyRequest `json:"request,omitempty"`

	// Status fields (from check results)
	HasFailures bool `json:"hasFailures"`
	HasErrors   bool `json:"hasErrors"`
}

// ChecklyRequest represents the request configuration for API checks
type ChecklyRequest struct {
	Method          string          `json:"method"`
	URL             string          `json:"url"`
	Headers         []ChecklyHeader `json:"headers,omitempty"`
	QueryParameters []ChecklyParam  `json:"queryParameters,omitempty"`
}

// ChecklyHeader represents a header in a Checkly request
type ChecklyHeader struct {
	Key    string `json:"key"`
	Value  string `json:"value"`
	Locked bool   `json:"locked"`
}

// ChecklyParam represents a query parameter
type ChecklyParam struct {
	Key    string `json:"key"`
	Value  string `json:"value"`
	Locked bool   `json:"locked"`
}

// ChecklyCheckResult represents the result of a check
type ChecklyCheckResult struct {
	ID                  string    `json:"id"`
	CheckID             string    `json:"checkId"`
	HasFailures         bool      `json:"hasFailures"`
	HasErrors           bool      `json:"hasErrors"`
	IsDegraded          bool      `json:"isDegraded"`
	OverMaxResponseTime bool      `json:"overMaxResponseTime"`
	RunLocation         string    `json:"runLocation"`
	StartedAt           time.Time `json:"startedAt"`
	StoppedAt           time.Time `json:"stoppedAt"`
	ResponseTime        int       `json:"responseTime"`
	Attempts            int       `json:"attempts"`
}

// ChecklyCheckStatus represents aggregated status for a check
type ChecklyCheckStatus struct {
	CheckID         string  `json:"checkId"`
	HasFailures     bool    `json:"hasFailures"`
	HasErrors       bool    `json:"hasErrors"`
	IsDegraded      bool    `json:"isDegraded"`
	LongestRun      int     `json:"longestRun"`
	ShortestRun     int     `json:"shortestRun"`
	AvgResponseTime int     `json:"avg"`
	Uptime24h       float64 `json:"uptime24h"`
	Uptime7d        float64 `json:"uptime7d"`
	Uptime30d       float64 `json:"uptime30d"`
}

// ChecklyAccountInfo represents account information
type ChecklyAccountInfo struct {
	ID   string `json:"id"`
	Name string `json:"name"`
}

// doRequest performs an authenticated request to Checkly API
func (c *ChecklyClient) doRequest(method, endpoint string) ([]byte, error) {
	req, err := http.NewRequest(method, ChecklyAPIURL+endpoint, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Authorization", "Bearer "+c.apiKey)
	req.Header.Set("X-Checkly-Account", c.accountID)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to call Checkly API: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("Checkly API error: status %d, body: %s", resp.StatusCode, string(body))
	}

	return body, nil
}

// ValidateCredentials validates API key and account ID by fetching checks
func (c *ChecklyClient) ValidateCredentials() error {
	_, err := c.doRequest("GET", "/checks?limit=1")
	if err != nil {
		return fmt.Errorf("invalid Checkly credentials: %w", err)
	}
	return nil
}

// GetChecks fetches all checks from Checkly
func (c *ChecklyClient) GetChecks() ([]ChecklyCheck, error) {
	var allChecks []ChecklyCheck
	page := 1
	limit := 100

	for {
		endpoint := fmt.Sprintf("/checks?page=%d&limit=%d", page, limit)
		body, err := c.doRequest("GET", endpoint)
		if err != nil {
			return nil, err
		}

		var checks []ChecklyCheck
		if err := json.Unmarshal(body, &checks); err != nil {
			return nil, fmt.Errorf("failed to parse response: %w", err)
		}

		allChecks = append(allChecks, checks...)

		// If we got fewer than limit, we've fetched all
		if len(checks) < limit {
			break
		}
		page++
	}

	return allChecks, nil
}

// GetCheckStatus fetches the latest status/results for a check
func (c *ChecklyClient) GetCheckStatus(checkID string) (*ChecklyCheckStatus, error) {
	// Get recent results
	endpoint := fmt.Sprintf("/check-results/%s?limit=1", checkID)
	body, err := c.doRequest("GET", endpoint)
	if err != nil {
		return nil, err
	}

	var results []ChecklyCheckResult
	if err := json.Unmarshal(body, &results); err != nil {
		return nil, fmt.Errorf("failed to parse results: %w", err)
	}

	status := &ChecklyCheckStatus{
		CheckID: checkID,
	}

	if len(results) > 0 {
		latest := results[0]
		status.HasFailures = latest.HasFailures
		status.HasErrors = latest.HasErrors
		status.IsDegraded = latest.IsDegraded
		status.AvgResponseTime = latest.ResponseTime
	}

	return status, nil
}

// GetCheckStatistics fetches uptime statistics for a check
func (c *ChecklyClient) GetCheckStatistics(checkID string, from, to time.Time) (*ChecklyCheckStatus, error) {
	endpoint := fmt.Sprintf("/check-statuses/%s?from=%d&to=%d",
		checkID,
		from.Unix()*1000,
		to.Unix()*1000,
	)

	body, err := c.doRequest("GET", endpoint)
	if err != nil {
		// If stats endpoint fails, return basic status
		return &ChecklyCheckStatus{CheckID: checkID}, nil
	}

	var stats []struct {
		CheckID      string  `json:"checkId"`
		HasFailures  bool    `json:"hasFailures"`
		HasErrors    bool    `json:"hasErrors"`
		LongestRun   int     `json:"longestRun"`
		ShortestRun  int     `json:"shortestRun"`
		Avg          int     `json:"avg"`
		SuccessRatio float64 `json:"successRatio"`
	}

	if err := json.Unmarshal(body, &stats); err != nil {
		return &ChecklyCheckStatus{CheckID: checkID}, nil
	}

	status := &ChecklyCheckStatus{CheckID: checkID}
	if len(stats) > 0 {
		s := stats[0]
		status.HasFailures = s.HasFailures
		status.HasErrors = s.HasErrors
		status.LongestRun = s.LongestRun
		status.ShortestRun = s.ShortestRun
		status.AvgResponseTime = s.Avg
		// Convert success ratio to uptime percentage
		status.Uptime30d = s.SuccessRatio * 100
		status.Uptime7d = s.SuccessRatio * 100
		status.Uptime24h = s.SuccessRatio * 100
	}

	return status, nil
}

// GetChecklyStatus converts Checkly check state to status string
func GetChecklyStatus(check ChecklyCheck, hasFailures, hasErrors, isDegraded bool) string {
	if !check.Activated {
		return "paused"
	}
	if check.Muted {
		return "muted"
	}
	if hasErrors || hasFailures {
		return "down"
	}
	if isDegraded {
		return "degraded"
	}
	return "up"
}

// GetChecklyMonitorType converts Checkly check type to standard type
func GetChecklyMonitorType(checkType string) string {
	switch checkType {
	case "API":
		return "http"
	case "BROWSER":
		return "browser"
	case "HEARTBEAT":
		return "heartbeat"
	default:
		return "unknown"
	}
}
