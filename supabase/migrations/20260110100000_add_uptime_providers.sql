-- Migration: Add support for external uptime monitoring providers
-- Supports: UptimeRobot, Checkly, Pingdom, Better Stack, Custom Webhooks

-- Table for external uptime providers configuration
CREATE TABLE IF NOT EXISTS uptime_providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    provider_type VARCHAR(50) NOT NULL, -- 'uptimerobot', 'checkly', 'pingdom', 'betterstack', 'webhook'
    api_key_encrypted TEXT, -- Encrypted API key
    webhook_secret TEXT, -- For webhook-based providers
    config JSONB DEFAULT '{}', -- Provider-specific configuration
    is_active BOOLEAN DEFAULT true,
    last_sync_at TIMESTAMP WITH TIME ZONE,
    sync_interval_minutes INT DEFAULT 5, -- How often to sync
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES users(id) ON DELETE SET NULL
);

-- Table for monitors imported from external providers
CREATE TABLE IF NOT EXISTS external_monitors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID NOT NULL REFERENCES uptime_providers(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    external_id VARCHAR(255) NOT NULL, -- ID from the external provider
    name VARCHAR(255) NOT NULL,
    url TEXT,
    monitor_type VARCHAR(50), -- 'http', 'https', 'ping', 'port', 'keyword', 'heartbeat'
    status VARCHAR(20) DEFAULT 'unknown', -- 'up', 'down', 'paused', 'unknown'
    is_paused BOOLEAN DEFAULT false,
    uptime_24h DECIMAL(5,2), -- Last 24 hours uptime %
    uptime_7d DECIMAL(5,2), -- Last 7 days uptime %
    uptime_30d DECIMAL(5,2), -- Last 30 days uptime %
    uptime_all_time DECIMAL(5,2), -- All time uptime %
    last_check_at TIMESTAMP WITH TIME ZONE,
    response_time_ms INT,
    ssl_expiry_date DATE,
    metadata JSONB DEFAULT '{}', -- Provider-specific data
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(provider_id, external_id)
);

-- Unified uptime history for all providers (daily aggregates)
CREATE TABLE IF NOT EXISTS uptime_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    monitor_id UUID NOT NULL, -- Can reference monitors or external_monitors
    monitor_source VARCHAR(20) NOT NULL, -- 'internal' (cloudflare) or 'external'
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    uptime_percent DECIMAL(5,2),
    total_checks INT DEFAULT 0,
    successful_checks INT DEFAULT 0,
    failed_checks INT DEFAULT 0,
    avg_response_ms INT,
    min_response_ms INT,
    max_response_ms INT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(monitor_id, monitor_source, date)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_uptime_providers_org ON uptime_providers(organization_id);
CREATE INDEX IF NOT EXISTS idx_uptime_providers_type ON uptime_providers(provider_type);
CREATE INDEX IF NOT EXISTS idx_external_monitors_provider ON external_monitors(provider_id);
CREATE INDEX IF NOT EXISTS idx_external_monitors_org ON external_monitors(organization_id);
CREATE INDEX IF NOT EXISTS idx_external_monitors_status ON external_monitors(status);
CREATE INDEX IF NOT EXISTS idx_uptime_history_monitor ON uptime_history(monitor_id, monitor_source);
CREATE INDEX IF NOT EXISTS idx_uptime_history_date ON uptime_history(date DESC);
CREATE INDEX IF NOT EXISTS idx_uptime_history_org ON uptime_history(organization_id);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_uptime_providers_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_uptime_providers_updated_at
    BEFORE UPDATE ON uptime_providers
    FOR EACH ROW
    EXECUTE FUNCTION update_uptime_providers_updated_at();

CREATE TRIGGER trigger_external_monitors_updated_at
    BEFORE UPDATE ON external_monitors
    FOR EACH ROW
    EXECUTE FUNCTION update_uptime_providers_updated_at();

-- Comments for documentation
COMMENT ON TABLE uptime_providers IS 'External uptime monitoring providers (UptimeRobot, Checkly, etc.)';
COMMENT ON TABLE external_monitors IS 'Monitors imported from external providers';
COMMENT ON TABLE uptime_history IS 'Daily uptime history for all monitors (internal and external)';
COMMENT ON COLUMN uptime_providers.provider_type IS 'Provider type: uptimerobot, checkly, pingdom, betterstack, webhook';
COMMENT ON COLUMN uptime_history.monitor_source IS 'Source: internal (Cloudflare Worker) or external (imported)';
