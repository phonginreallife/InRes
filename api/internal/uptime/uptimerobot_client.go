package uptime

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

const (
	UptimeRobotAPIURL = "https://api.uptimerobot.com/v2"
)

// UptimeRobotClient handles communication with UptimeRobot API
type UptimeRobotClient struct {
	apiKey     string
	httpClient *http.Client
}

// NewUptimeRobotClient creates a new UptimeRobot API client
func NewUptimeRobotClient(apiKey string) *UptimeRobotClient {
	return &UptimeRobotClient{
		apiKey: apiKey,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// UptimeRobotMonitor represents a monitor from UptimeRobot
type UptimeRobotMonitor struct {
	ID                  int64           `json:"id"`
	FriendlyName        string          `json:"friendly_name"`
	URL                 string          `json:"url"`
	Type                int             `json:"type"`                            // 1=HTTP(s), 2=Keyword, 3=Ping, 4=Port, 5=Heartbeat
	Status              int             `json:"status"`                          // 0=paused, 1=not checked, 2=up, 8=seems down, 9=down
	Interval            int             `json:"interval"`                        // in seconds
	SSL                 json.RawMessage `json:"ssl,omitempty"`                   // Can be object or null
	AverageResponseTime json.Number     `json:"average_response_time,omitempty"` // Can be string or number
	UptimeRatio24h      string          `json:"custom_uptime_ratio"`             // Will be parsed from custom_uptime_ranges
	CreateDatetime      int64           `json:"create_datetime"`

	// Custom uptime ratios (if requested)
	CustomUptimeRanges string `json:"custom_uptime_ranges,omitempty"`
}

// UptimeRobotResponse represents the API response
type UptimeRobotResponse struct {
	Stat       string               `json:"stat"` // "ok" or "fail"
	Error      *UptimeRobotError    `json:"error,omitempty"`
	Monitors   []UptimeRobotMonitor `json:"monitors,omitempty"`
	Pagination struct {
		Offset int `json:"offset"`
		Limit  int `json:"limit"`
		Total  int `json:"total"`
	} `json:"pagination,omitempty"`
}

// UptimeRobotError represents an API error
type UptimeRobotError struct {
	Type    string `json:"type"`
	Message string `json:"message"`
}

// UptimeRobotAccountDetails represents account information
type UptimeRobotAccountDetails struct {
	Email           string `json:"email"`
	MonitorLimit    int    `json:"monitor_limit"`
	MonitorInterval int    `json:"monitor_interval"`
	UpMonitors      int    `json:"up_monitors"`
	DownMonitors    int    `json:"down_monitors"`
	PausedMonitors  int    `json:"paused_monitors"`
}

// GetAccountDetails fetches account information to verify API key
func (c *UptimeRobotClient) GetAccountDetails() (*UptimeRobotAccountDetails, error) {
	data := url.Values{}
	data.Set("api_key", c.apiKey)
	data.Set("format", "json")

	resp, err := c.httpClient.PostForm(UptimeRobotAPIURL+"/getAccountDetails", data)
	if err != nil {
		return nil, fmt.Errorf("failed to call UptimeRobot API: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	var result struct {
		Stat    string                    `json:"stat"`
		Error   *UptimeRobotError         `json:"error,omitempty"`
		Account UptimeRobotAccountDetails `json:"account,omitempty"`
	}
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	if result.Stat != "ok" {
		if result.Error != nil {
			return nil, fmt.Errorf("UptimeRobot API error: %s", result.Error.Message)
		}
		return nil, fmt.Errorf("UptimeRobot API returned error status")
	}

	return &result.Account, nil
}

// GetMonitors fetches all monitors from UptimeRobot
func (c *UptimeRobotClient) GetMonitors() ([]UptimeRobotMonitor, error) {
	var allMonitors []UptimeRobotMonitor
	offset := 0
	limit := 50

	for {
		data := url.Values{}
		data.Set("api_key", c.apiKey)
		data.Set("format", "json")
		data.Set("offset", fmt.Sprintf("%d", offset))
		data.Set("limit", fmt.Sprintf("%d", limit))
		data.Set("response_times", "1")
		data.Set("response_times_limit", "1")
		// Request custom uptime ratios: 1 day, 7 days, 30 days
		data.Set("custom_uptime_ratios", "1-7-30")
		data.Set("ssl", "1") // Include SSL info

		resp, err := c.httpClient.PostForm(UptimeRobotAPIURL+"/getMonitors", data)
		if err != nil {
			return nil, fmt.Errorf("failed to call UptimeRobot API: %w", err)
		}
		defer resp.Body.Close()

		body, err := io.ReadAll(resp.Body)
		if err != nil {
			return nil, fmt.Errorf("failed to read response: %w", err)
		}

		var result UptimeRobotResponse
		if err := json.Unmarshal(body, &result); err != nil {
			return nil, fmt.Errorf("failed to parse response: %w", err)
		}

		if result.Stat != "ok" {
			if result.Error != nil {
				return nil, fmt.Errorf("UptimeRobot API error: %s", result.Error.Message)
			}
			return nil, fmt.Errorf("UptimeRobot API returned error status")
		}

		allMonitors = append(allMonitors, result.Monitors...)

		// Check if we've fetched all monitors
		if offset+limit >= result.Pagination.Total {
			break
		}
		offset += limit
	}

	return allMonitors, nil
}

// GetMonitorStatus converts UptimeRobot status code to string
func GetMonitorStatus(status int) string {
	switch status {
	case 0:
		return "paused"
	case 1:
		return "unknown"
	case 2:
		return "up"
	case 8:
		return "degraded"
	case 9:
		return "down"
	default:
		return "unknown"
	}
}

// GetMonitorType converts UptimeRobot monitor type code to string
func GetMonitorType(monitorType int) string {
	switch monitorType {
	case 1:
		return "http"
	case 2:
		return "keyword"
	case 3:
		return "ping"
	case 4:
		return "port"
	case 5:
		return "heartbeat"
	default:
		return "unknown"
	}
}

// ParseUptimeRatios parses the custom_uptime_ranges string
// Format: "ratio1-ratio2-ratio3" (1d-7d-30d)
func ParseUptimeRatios(ratios string) (day1, day7, day30, allTime float64) {
	if ratios == "" {
		return 0, 0, 0, 0
	}

	parts := strings.Split(ratios, "-")
	if len(parts) >= 1 {
		_, _ = fmt.Sscanf(parts[0], "%f", &day1)
	}
	if len(parts) >= 2 {
		_, _ = fmt.Sscanf(parts[1], "%f", &day7)
	}
	if len(parts) >= 3 {
		_, _ = fmt.Sscanf(parts[2], "%f", &day30)
	}
	// Use 30-day as all-time approximation
	allTime = day30

	return day1, day7, day30, allTime
}
