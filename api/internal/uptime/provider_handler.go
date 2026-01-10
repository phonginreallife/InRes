package uptime

import (
	"database/sql"
	"fmt"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

// ProviderHandler handles uptime provider API requests
type ProviderHandler struct {
	db *sql.DB
}

// NewProviderHandler creates a new provider handler
func NewProviderHandler(db *sql.DB) *ProviderHandler {
	return &ProviderHandler{db: db}
}

// Provider types
const (
	ProviderTypeUptimeRobot = "uptimerobot"
	ProviderTypeCheckly     = "checkly"
	ProviderTypePingdom     = "pingdom"
	ProviderTypeBetterStack = "betterstack"
	ProviderTypeWebhook     = "webhook"
)

// UptimeProvider represents a configured uptime provider
type UptimeProvider struct {
	ID                  uuid.UUID  `json:"id"`
	OrganizationID      *uuid.UUID `json:"organization_id,omitempty"`
	Name                string     `json:"name"`
	ProviderType        string     `json:"provider_type"`
	APIKey              string     `json:"api_key,omitempty"` // Only for input, never returned
	IsActive            bool       `json:"is_active"`
	LastSyncAt          *time.Time `json:"last_sync_at,omitempty"`
	SyncIntervalMinutes int        `json:"sync_interval_minutes"`
	MonitorCount        int        `json:"monitor_count,omitempty"`
	CreatedAt           time.Time  `json:"created_at"`
	UpdatedAt           time.Time  `json:"updated_at"`
}

// ExternalMonitor represents a monitor from an external provider
type ExternalMonitor struct {
	ID             uuid.UUID  `json:"id"`
	ProviderID     uuid.UUID  `json:"provider_id"`
	OrganizationID *uuid.UUID `json:"organization_id,omitempty"`
	ExternalID     string     `json:"external_id"`
	Name           string     `json:"name"`
	URL            string     `json:"url"`
	MonitorType    string     `json:"monitor_type"`
	Status         string     `json:"status"`
	IsPaused       bool       `json:"is_paused"`
	Uptime24h      float64    `json:"uptime_24h"`
	Uptime7d       float64    `json:"uptime_7d"`
	Uptime30d      float64    `json:"uptime_30d"`
	UptimeAllTime  float64    `json:"uptime_all_time"`
	LastCheckAt    *time.Time `json:"last_check_at,omitempty"`
	ResponseTimeMs int        `json:"response_time_ms"`
	ProviderType   string     `json:"provider_type,omitempty"` // Joined from provider
	ProviderName   string     `json:"provider_name,omitempty"` // Joined from provider
	CreatedAt      time.Time  `json:"created_at"`
	UpdatedAt      time.Time  `json:"updated_at"`
}

// CreateProviderRequest represents the request to create a provider
type CreateProviderRequest struct {
	Name                string `json:"name" binding:"required"`
	ProviderType        string `json:"provider_type" binding:"required"`
	APIKey              string `json:"api_key" binding:"required"`
	OrganizationID      string `json:"organization_id"`
	SyncIntervalMinutes int    `json:"sync_interval_minutes"`
}

// ListProviders returns all configured uptime providers
func (h *ProviderHandler) ListProviders(c *gin.Context) {
	orgID := c.Query("org_id")
	if orgID == "" {
		orgID = c.GetHeader("X-Org-ID")
	}

	var query string
	var args []interface{}

	if orgID != "" {
		query = `
			SELECT p.id, p.organization_id, p.name, p.provider_type, p.is_active, 
			       p.last_sync_at, p.sync_interval_minutes, p.created_at, p.updated_at,
			       COALESCE(m.monitor_count, 0) as monitor_count
			FROM uptime_providers p
			LEFT JOIN (
				SELECT provider_id, COUNT(*) as monitor_count
				FROM external_monitors
				GROUP BY provider_id
			) m ON p.id = m.provider_id
			WHERE p.organization_id = $1
			ORDER BY p.created_at DESC
		`
		args = append(args, orgID)
	} else {
		query = `
			SELECT p.id, p.organization_id, p.name, p.provider_type, p.is_active, 
			       p.last_sync_at, p.sync_interval_minutes, p.created_at, p.updated_at,
			       COALESCE(m.monitor_count, 0) as monitor_count
			FROM uptime_providers p
			LEFT JOIN (
				SELECT provider_id, COUNT(*) as monitor_count
				FROM external_monitors
				GROUP BY provider_id
			) m ON p.id = m.provider_id
			ORDER BY p.created_at DESC
		`
	}

	rows, err := h.db.Query(query, args...)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	defer rows.Close()

	providers := []UptimeProvider{}
	for rows.Next() {
		var p UptimeProvider
		var orgID sql.NullString
		var lastSyncAt sql.NullTime

		err := rows.Scan(
			&p.ID, &orgID, &p.Name, &p.ProviderType, &p.IsActive,
			&lastSyncAt, &p.SyncIntervalMinutes, &p.CreatedAt, &p.UpdatedAt,
			&p.MonitorCount,
		)
		if err != nil {
			continue
		}

		if orgID.Valid {
			id, _ := uuid.Parse(orgID.String)
			p.OrganizationID = &id
		}
		if lastSyncAt.Valid {
			p.LastSyncAt = &lastSyncAt.Time
		}

		providers = append(providers, p)
	}

	c.JSON(http.StatusOK, providers)
}

// CreateProvider adds a new uptime provider
func (h *ProviderHandler) CreateProvider(c *gin.Context) {
	var req CreateProviderRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Validate provider type
	validTypes := map[string]bool{
		ProviderTypeUptimeRobot: true,
		ProviderTypeCheckly:     true,
		ProviderTypePingdom:     true,
		ProviderTypeBetterStack: true,
		ProviderTypeWebhook:     true,
	}
	if !validTypes[req.ProviderType] {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid provider type"})
		return
	}

	// Get organization ID
	orgIDStr := req.OrganizationID
	if orgIDStr == "" {
		orgIDStr = c.Query("org_id")
	}
	if orgIDStr == "" {
		orgIDStr = c.GetHeader("X-Org-ID")
	}

	var orgIDPtr *string
	if orgIDStr != "" {
		orgIDPtr = &orgIDStr
	}

	// Verify API key by fetching account details
	if req.ProviderType == ProviderTypeUptimeRobot {
		client := NewUptimeRobotClient(req.APIKey)
		account, err := client.GetAccountDetails()
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"error":   "Invalid API key",
				"details": err.Error(),
			})
			return
		}
		fmt.Printf("[UptimeRobot] Verified account: %s (up: %d, down: %d, paused: %d)\n",
			account.Email, account.UpMonitors, account.DownMonitors, account.PausedMonitors)
	} else if req.ProviderType == ProviderTypeCheckly {
		// Checkly requires both API key and Account ID (format: "apikey:accountid")
		parts := splitChecklyCredentials(req.APIKey)
		if len(parts) != 2 {
			c.JSON(http.StatusBadRequest, gin.H{
				"error":   "Invalid Checkly credentials format",
				"details": "Please provide credentials in format: API_KEY:ACCOUNT_ID",
			})
			return
		}
		client := NewChecklyClient(parts[0], parts[1])
		err := client.ValidateCredentials()
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"error":   "Invalid Checkly credentials",
				"details": err.Error(),
			})
			return
		}
		fmt.Printf("[Checkly] Verified account: %s\n", parts[1])
	}

	// Set default sync interval
	syncInterval := req.SyncIntervalMinutes
	if syncInterval <= 0 {
		syncInterval = 5
	}

	// Insert provider
	var providerID uuid.UUID
	err := h.db.QueryRow(`
		INSERT INTO uptime_providers (name, provider_type, api_key_encrypted, organization_id, sync_interval_minutes, is_active)
		VALUES ($1, $2, $3, $4, $5, true)
		RETURNING id
	`, req.Name, req.ProviderType, req.APIKey, orgIDPtr, syncInterval).Scan(&providerID)

	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create provider: " + err.Error()})
		return
	}

	// Immediately sync monitors
	go h.syncProvider(providerID)

	c.JSON(http.StatusCreated, gin.H{
		"id":            providerID,
		"name":          req.Name,
		"provider_type": req.ProviderType,
		"message":       "Provider created. Syncing monitors in background...",
	})
}

// DeleteProvider removes a provider and all its monitors
func (h *ProviderHandler) DeleteProvider(c *gin.Context) {
	providerID := c.Param("id")

	// Delete provider (cascades to external_monitors)
	result, err := h.db.Exec(`DELETE FROM uptime_providers WHERE id = $1`, providerID)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	rowsAffected, _ := result.RowsAffected()
	if rowsAffected == 0 {
		c.JSON(http.StatusNotFound, gin.H{"error": "Provider not found"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "Provider deleted"})
}

// SyncProvider manually triggers a sync for a provider
func (h *ProviderHandler) SyncProvider(c *gin.Context) {
	providerID := c.Param("id")

	id, err := uuid.Parse(providerID)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid provider ID"})
		return
	}

	// Sync in background
	go h.syncProvider(id)

	c.JSON(http.StatusOK, gin.H{"message": "Sync started"})
}

// syncProvider syncs monitors from an external provider
func (h *ProviderHandler) syncProvider(providerID uuid.UUID) {
	// Get provider details
	var providerType, apiKey string
	var orgID sql.NullString
	err := h.db.QueryRow(`
		SELECT provider_type, api_key_encrypted, organization_id
		FROM uptime_providers WHERE id = $1
	`, providerID).Scan(&providerType, &apiKey, &orgID)

	if err != nil {
		fmt.Printf("[Uptime Sync] Error getting provider %s: %v\n", providerID, err)
		return
	}

	fmt.Printf("[Uptime Sync] Starting sync for provider %s (type: %s)\n", providerID, providerType)

	switch providerType {
	case ProviderTypeUptimeRobot:
		h.syncUptimeRobot(providerID, apiKey, orgID)
	case ProviderTypeCheckly:
		h.syncCheckly(providerID, apiKey, orgID)
	default:
		fmt.Printf("[Uptime Sync] Provider type %s not yet implemented\n", providerType)
	}

	// Update last sync time
	h.db.Exec(`UPDATE uptime_providers SET last_sync_at = NOW() WHERE id = $1`, providerID)
}

// syncUptimeRobot syncs monitors from UptimeRobot
func (h *ProviderHandler) syncUptimeRobot(providerID uuid.UUID, apiKey string, orgID sql.NullString) {
	client := NewUptimeRobotClient(apiKey)
	monitors, err := client.GetMonitors()
	if err != nil {
		fmt.Printf("[UptimeRobot Sync] Error fetching monitors: %v\n", err)
		return
	}

	fmt.Printf("[UptimeRobot Sync] Found %d monitors\n", len(monitors))

	for _, m := range monitors {
		status := GetMonitorStatus(m.Status)
		monitorType := GetMonitorType(m.Type)
		uptime1d, uptime7d, uptime30d, uptimeAll := ParseUptimeRatios(m.CustomUptimeRanges)

		var lastCheckAt *time.Time
		if m.CreateDatetime > 0 {
			t := time.Unix(m.CreateDatetime, 0)
			lastCheckAt = &t
		}

		// Convert json.Number to int
		avgResponseTime := 0
		if m.AverageResponseTime != "" {
			if val, err := m.AverageResponseTime.Int64(); err == nil {
				avgResponseTime = int(val)
			}
		}

		// Upsert monitor
		_, err := h.db.Exec(`
			INSERT INTO external_monitors (
				provider_id, organization_id, external_id, name, url, monitor_type,
				status, is_paused, uptime_24h, uptime_7d, uptime_30d, uptime_all_time,
				last_check_at, response_time_ms
			) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
			ON CONFLICT (provider_id, external_id) DO UPDATE SET
				name = EXCLUDED.name,
				url = EXCLUDED.url,
				monitor_type = EXCLUDED.monitor_type,
				status = EXCLUDED.status,
				is_paused = EXCLUDED.is_paused,
				uptime_24h = EXCLUDED.uptime_24h,
				uptime_7d = EXCLUDED.uptime_7d,
				uptime_30d = EXCLUDED.uptime_30d,
				uptime_all_time = EXCLUDED.uptime_all_time,
				last_check_at = EXCLUDED.last_check_at,
				response_time_ms = EXCLUDED.response_time_ms,
				updated_at = NOW()
		`,
			providerID,
			orgID,
			fmt.Sprintf("%d", m.ID),
			m.FriendlyName,
			m.URL,
			monitorType,
			status,
			m.Status == 0, // paused
			uptime1d,
			uptime7d,
			uptime30d,
			uptimeAll,
			lastCheckAt,
			avgResponseTime,
		)

		if err != nil {
			fmt.Printf("[UptimeRobot Sync] Error upserting monitor %s: %v\n", m.FriendlyName, err)
		}
	}

	fmt.Printf("[UptimeRobot Sync] Sync complete for provider %s\n", providerID)
}

// splitChecklyCredentials splits "apikey:accountid" format
func splitChecklyCredentials(combined string) []string {
	parts := make([]string, 0, 2)
	idx := -1
	// Find the last colon (account IDs don't have colons, but API keys might)
	for i := len(combined) - 1; i >= 0; i-- {
		if combined[i] == ':' {
			idx = i
			break
		}
	}
	if idx > 0 && idx < len(combined)-1 {
		parts = append(parts, combined[:idx])
		parts = append(parts, combined[idx+1:])
	}
	return parts
}

// syncCheckly syncs monitors from Checkly
func (h *ProviderHandler) syncCheckly(providerID uuid.UUID, apiKey string, orgID sql.NullString) {
	// Parse credentials
	parts := splitChecklyCredentials(apiKey)
	if len(parts) != 2 {
		fmt.Printf("[Checkly Sync] Invalid credentials format for provider %s\n", providerID)
		return
	}

	client := NewChecklyClient(parts[0], parts[1])
	checks, err := client.GetChecks()
	if err != nil {
		fmt.Printf("[Checkly Sync] Error fetching checks: %v\n", err)
		return
	}

	fmt.Printf("[Checkly Sync] Found %d checks\n", len(checks))

	for _, check := range checks {
		// Get check status/statistics
		stats, err := client.GetCheckStatistics(check.ID, time.Now().AddDate(0, 0, -30), time.Now())
		if err != nil {
			fmt.Printf("[Checkly Sync] Error getting stats for %s: %v\n", check.Name, err)
		}

		// Determine URL
		checkURL := ""
		if check.Request != nil {
			checkURL = check.Request.URL
		}

		// Determine status
		status := GetChecklyStatus(check, stats.HasFailures, stats.HasErrors, stats.IsDegraded)
		monitorType := GetChecklyMonitorType(check.CheckType)

		// Upsert monitor
		_, err = h.db.Exec(`
			INSERT INTO external_monitors (
				provider_id, organization_id, external_id, name, url, monitor_type,
				status, is_paused, uptime_24h, uptime_7d, uptime_30d, uptime_all_time,
				response_time_ms
			) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
			ON CONFLICT (provider_id, external_id) DO UPDATE SET
				name = EXCLUDED.name,
				url = EXCLUDED.url,
				monitor_type = EXCLUDED.monitor_type,
				status = EXCLUDED.status,
				is_paused = EXCLUDED.is_paused,
				uptime_24h = EXCLUDED.uptime_24h,
				uptime_7d = EXCLUDED.uptime_7d,
				uptime_30d = EXCLUDED.uptime_30d,
				uptime_all_time = EXCLUDED.uptime_all_time,
				response_time_ms = EXCLUDED.response_time_ms,
				updated_at = NOW()
		`,
			providerID,
			orgID,
			check.ID,
			check.Name,
			checkURL,
			monitorType,
			status,
			!check.Activated || check.Muted,
			stats.Uptime24h,
			stats.Uptime7d,
			stats.Uptime30d,
			stats.Uptime30d, // Use 30d as all-time approximation
			stats.AvgResponseTime,
		)

		if err != nil {
			fmt.Printf("[Checkly Sync] Error upserting check %s: %v\n", check.Name, err)
		}
	}

	fmt.Printf("[Checkly Sync] Sync complete for provider %s\n", providerID)
}

// ListExternalMonitors returns all external monitors
func (h *ProviderHandler) ListExternalMonitors(c *gin.Context) {
	orgID := c.Query("org_id")
	if orgID == "" {
		orgID = c.GetHeader("X-Org-ID")
	}
	providerID := c.Query("provider_id")

	var conditions []string
	var args []interface{}
	argIdx := 1

	if orgID != "" {
		conditions = append(conditions, fmt.Sprintf("m.organization_id = $%d", argIdx))
		args = append(args, orgID)
		argIdx++
	}
	if providerID != "" {
		conditions = append(conditions, fmt.Sprintf("m.provider_id = $%d", argIdx))
		args = append(args, providerID)
		argIdx++
	}

	query := `
		SELECT m.id, m.provider_id, m.organization_id, m.external_id, m.name, m.url,
		       m.monitor_type, m.status, m.is_paused, m.uptime_24h, m.uptime_7d,
		       m.uptime_30d, m.uptime_all_time, m.last_check_at, m.response_time_ms,
		       m.created_at, m.updated_at,
		       p.provider_type, p.name as provider_name
		FROM external_monitors m
		JOIN uptime_providers p ON m.provider_id = p.id
	`

	if len(conditions) > 0 {
		query += " WHERE " + conditions[0]
		for i := 1; i < len(conditions); i++ {
			query += " AND " + conditions[i]
		}
	}
	query += " ORDER BY m.name ASC"

	rows, err := h.db.Query(query, args...)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	defer rows.Close()

	monitors := []ExternalMonitor{}
	for rows.Next() {
		var m ExternalMonitor
		var orgID sql.NullString
		var lastCheckAt sql.NullTime

		err := rows.Scan(
			&m.ID, &m.ProviderID, &orgID, &m.ExternalID, &m.Name, &m.URL,
			&m.MonitorType, &m.Status, &m.IsPaused, &m.Uptime24h, &m.Uptime7d,
			&m.Uptime30d, &m.UptimeAllTime, &lastCheckAt, &m.ResponseTimeMs,
			&m.CreatedAt, &m.UpdatedAt, &m.ProviderType, &m.ProviderName,
		)
		if err != nil {
			continue
		}

		if orgID.Valid {
			id, _ := uuid.Parse(orgID.String)
			m.OrganizationID = &id
		}
		if lastCheckAt.Valid {
			m.LastCheckAt = &lastCheckAt.Time
		}

		monitors = append(monitors, m)
	}

	c.JSON(http.StatusOK, monitors)
}

// GetAllMonitors returns both internal (Cloudflare) and external monitors unified
func (h *ProviderHandler) GetAllMonitors(c *gin.Context) {
	orgID := c.Query("org_id")
	if orgID == "" {
		orgID = c.GetHeader("X-Org-ID")
	}

	type UnifiedMonitor struct {
		ID             string     `json:"id"`
		Name           string     `json:"name"`
		URL            string     `json:"url"`
		MonitorType    string     `json:"monitor_type"`
		Status         string     `json:"status"`
		Source         string     `json:"source"`      // 'cloudflare' or provider type
		SourceName     string     `json:"source_name"` // Display name
		Uptime24h      float64    `json:"uptime_24h"`
		Uptime7d       float64    `json:"uptime_7d"`
		Uptime30d      float64    `json:"uptime_30d"`
		ResponseTimeMs int        `json:"response_time_ms"`
		LastCheckAt    *time.Time `json:"last_check_at,omitempty"`
	}

	monitors := []UnifiedMonitor{}

	// Fetch internal monitors (Cloudflare Workers)
	internalQuery := `
		SELECT m.id, m.name, m.url, m.method, 
		       CASE WHEN m.is_up = true THEN 'up' WHEN m.is_up = false THEN 'down' ELSE 'unknown' END as status,
		       m.last_latency, m.last_check_at
		FROM monitors m
	`
	if orgID != "" {
		internalQuery += " WHERE m.organization_id = $1"
	}

	var internalArgs []interface{}
	if orgID != "" {
		internalArgs = append(internalArgs, orgID)
	}

	rows, err := h.db.Query(internalQuery, internalArgs...)
	if err == nil {
		defer rows.Close()
		for rows.Next() {
			var m UnifiedMonitor
			var lastLatency sql.NullInt64
			var lastCheckAt sql.NullTime

			err := rows.Scan(&m.ID, &m.Name, &m.URL, &m.MonitorType, &m.Status, &lastLatency, &lastCheckAt)
			if err != nil {
				continue
			}

			m.Source = "cloudflare"
			m.SourceName = "Cloudflare Worker"
			if lastLatency.Valid {
				m.ResponseTimeMs = int(lastLatency.Int64)
			}
			if lastCheckAt.Valid {
				m.LastCheckAt = &lastCheckAt.Time
			}

			monitors = append(monitors, m)
		}
	}

	// Fetch external monitors
	externalQuery := `
		SELECT m.id, m.name, m.url, m.monitor_type, m.status,
		       m.uptime_24h, m.uptime_7d, m.uptime_30d, m.response_time_ms, m.last_check_at,
		       p.provider_type, p.name as provider_name
		FROM external_monitors m
		JOIN uptime_providers p ON m.provider_id = p.id
		WHERE p.is_active = true
	`
	if orgID != "" {
		externalQuery += " AND m.organization_id = $1"
	}

	var externalArgs []interface{}
	if orgID != "" {
		externalArgs = append(externalArgs, orgID)
	}

	rows2, err := h.db.Query(externalQuery, externalArgs...)
	if err == nil {
		defer rows2.Close()
		for rows2.Next() {
			var m UnifiedMonitor
			var lastCheckAt sql.NullTime

			err := rows2.Scan(
				&m.ID, &m.Name, &m.URL, &m.MonitorType, &m.Status,
				&m.Uptime24h, &m.Uptime7d, &m.Uptime30d, &m.ResponseTimeMs, &lastCheckAt,
				&m.Source, &m.SourceName,
			)
			if err != nil {
				continue
			}

			if lastCheckAt.Valid {
				m.LastCheckAt = &lastCheckAt.Time
			}

			monitors = append(monitors, m)
		}
	}

	c.JSON(http.StatusOK, monitors)
}
