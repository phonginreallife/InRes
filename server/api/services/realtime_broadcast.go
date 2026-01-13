package services

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"time"

	"github.com/phonginreallife/inres/internal/config"
)

// RealtimeBroadcastService handles broadcasting notifications via Supabase Realtime
type RealtimeBroadcastService struct {
	supabaseURL string
	serviceKey  string
	httpClient  *http.Client
}

// BroadcastPayload represents the payload structure for Supabase Broadcast
type BroadcastPayload struct {
	Type    string      `json:"type"`
	Event   string      `json:"event"`
	Payload interface{} `json:"payload"`
}

// BroadcastRequest is the request body for Supabase Realtime broadcast API
type BroadcastRequest struct {
	Channel string           `json:"channel"`
	Event   string           `json:"event"`
	Payload BroadcastPayload `json:"payload"`
}

// NewRealtimeBroadcastService creates a new broadcast service
func NewRealtimeBroadcastService() *RealtimeBroadcastService {
	url := config.App.SupabaseURL
	key := config.App.SupabaseServiceRoleKey

	if url == "" || key == "" {
		log.Printf("Realtime broadcast service: Supabase not fully configured (URL: %v, Key set: %v)", url != "", key != "")
	} else {
		log.Printf("Realtime broadcast service configured for: %s", url)
	}

	return &RealtimeBroadcastService{
		supabaseURL: url,
		serviceKey:  key,
		httpClient: &http.Client{
			Timeout: 10 * time.Second,
		},
	}
}

// BroadcastIncident broadcasts an incident event to all connected clients in the organization
func (s *RealtimeBroadcastService) BroadcastIncident(orgID string, incident interface{}, eventType string) error {
	if s.supabaseURL == "" || s.serviceKey == "" {
		return nil
	}

	channel := fmt.Sprintf("org-notifications-%s", orgID)

	payload := map[string]interface{}{
		"data":      incident,
		"eventType": eventType,
	}

	return s.broadcast(channel, "incident", payload)
}

// BroadcastAlert broadcasts an alert event to all connected clients in the organization
func (s *RealtimeBroadcastService) BroadcastAlert(orgID string, alert interface{}) error {
	if s.supabaseURL == "" || s.serviceKey == "" {
		return nil
	}

	channel := fmt.Sprintf("org-notifications-%s", orgID)

	payload := map[string]interface{}{
		"data":      alert,
		"eventType": "INSERT",
	}

	return s.broadcast(channel, "alert", payload)
}

// BroadcastMonitorStatus broadcasts a monitor status change to all connected clients
func (s *RealtimeBroadcastService) BroadcastMonitorStatus(orgID string, monitor interface{}, oldStatus bool, newStatus bool) error {
	if s.supabaseURL == "" || s.serviceKey == "" {
		return nil
	}

	// Only broadcast on status change
	if oldStatus == newStatus {
		return nil
	}

	channel := fmt.Sprintf("org-notifications-%s", orgID)

	payload := map[string]interface{}{
		"data":    monitor,
		"oldData": map[string]interface{}{"is_up": oldStatus},
	}

	return s.broadcast(channel, "monitor", payload)
}

// broadcast sends a message to a Supabase Realtime channel
func (s *RealtimeBroadcastService) broadcast(channel, event string, payload interface{}) error {
	// Supabase Realtime broadcast endpoint
	// Using the REST API: POST /realtime/v1/api/broadcast
	url := fmt.Sprintf("%s/realtime/v1/api/broadcast", s.supabaseURL)

	// Supabase Realtime API expects messages array format
	reqBody := map[string]interface{}{
		"messages": []map[string]interface{}{
			{
				"topic":   channel,
				"event":   event,
				"payload": payload,
			},
		},
	}

	jsonBody, err := json.Marshal(reqBody)
	if err != nil {
		return fmt.Errorf("failed to marshal broadcast request: %w", err)
	}

	req, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonBody))
	if err != nil {
		return fmt.Errorf("failed to create broadcast request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("apikey", s.serviceKey)
	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", s.serviceKey))

	resp, err := s.httpClient.Do(req)
	if err != nil {
		log.Printf("Broadcast request failed: %v", err)
		return fmt.Errorf("broadcast request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		body, _ := io.ReadAll(resp.Body)
		log.Printf("Broadcast returned status %d for channel %s: %s", resp.StatusCode, channel, string(body))
		return fmt.Errorf("broadcast returned status %d: %s", resp.StatusCode, string(body))
	}

	log.Printf("Broadcasted %s event to channel %s", event, channel)
	return nil
}

// BroadcastIncidentAsync broadcasts an incident event asynchronously (non-blocking)
func (s *RealtimeBroadcastService) BroadcastIncidentAsync(orgID string, incident interface{}, eventType string) {
	go func() {
		if err := s.BroadcastIncident(orgID, incident, eventType); err != nil {
			log.Printf("Async broadcast failed: %v", err)
		}
	}()
}
