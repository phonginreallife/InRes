-- Migration: Add organization_id to monitor_deployments and monitors tables
-- This enables ReBAC-style tenant isolation for monitors

-- Add organization_id to monitor_deployments
ALTER TABLE monitor_deployments 
ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE;

-- Add organization_id to monitors table
ALTER TABLE monitors 
ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE;

-- Create indexes for faster org-based queries
CREATE INDEX IF NOT EXISTS idx_monitor_deployments_org_id ON monitor_deployments(organization_id);
CREATE INDEX IF NOT EXISTS idx_monitors_org_id ON monitors(organization_id);

-- Backfill organization_id from group_id for existing deployments
UPDATE monitor_deployments md
SET organization_id = (
    SELECT COALESCE(g.organization_id, p.organization_id)
    FROM groups g
    LEFT JOIN projects p ON g.project_id = p.id
    WHERE g.id = md.group_id
)
WHERE md.organization_id IS NULL AND md.group_id IS NOT NULL;

-- Add comments for documentation
COMMENT ON COLUMN monitor_deployments.organization_id IS 'Organization this deployment belongs to (for tenant isolation)';
COMMENT ON COLUMN monitors.organization_id IS 'Organization this monitor belongs to (for tenant isolation)';
