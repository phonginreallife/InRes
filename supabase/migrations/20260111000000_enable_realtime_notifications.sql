-- Enable Supabase Realtime for notification-relevant tables
-- This allows the frontend to subscribe to real-time changes
--
-- SECURITY NOTE: 
-- - All tables have RLS (Row Level Security) enabled
-- - Supabase Realtime respects RLS policies
-- - Users will only receive events for rows they have access to
-- - Organization isolation is enforced via get_user_organizations()

-- Enable realtime for incidents table (RLS enforced)
-- Only broadcasts to users who have SELECT access via RLS policies
DO $$
BEGIN
    -- Check if table is already in publication to make migration idempotent
    IF NOT EXISTS (
        SELECT 1 FROM pg_publication_tables 
        WHERE pubname = 'supabase_realtime' 
        AND tablename = 'incidents'
    ) THEN
        ALTER PUBLICATION supabase_realtime ADD TABLE incidents;
        RAISE NOTICE 'Added incidents table to supabase_realtime publication';
    ELSE
        RAISE NOTICE 'incidents table already in supabase_realtime publication';
    END IF;
END $$;

-- Enable realtime for alerts table (if exists, RLS enforced)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'alerts' AND table_schema = 'public') THEN
        IF NOT EXISTS (
            SELECT 1 FROM pg_publication_tables 
            WHERE pubname = 'supabase_realtime' 
            AND tablename = 'alerts'
        ) THEN
            ALTER PUBLICATION supabase_realtime ADD TABLE alerts;
            RAISE NOTICE 'Added alerts table to supabase_realtime publication';
        END IF;
    END IF;
END $$;

-- Enable realtime for monitors table (for service status notifications, RLS enforced)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'monitors' AND table_schema = 'public') THEN
        IF NOT EXISTS (
            SELECT 1 FROM pg_publication_tables 
            WHERE pubname = 'supabase_realtime' 
            AND tablename = 'monitors'
        ) THEN
            ALTER PUBLICATION supabase_realtime ADD TABLE monitors;
            RAISE NOTICE 'Added monitors table to supabase_realtime publication';
        END IF;
    END IF;
END $$;

-- Set REPLICA IDENTITY FULL so Supabase Realtime can broadcast all column values
-- This is required for postgres_changes to work properly
ALTER TABLE incidents REPLICA IDENTITY FULL;
ALTER TABLE alerts REPLICA IDENTITY FULL;
ALTER TABLE monitors REPLICA IDENTITY FULL;

-- Note: After running this migration, the frontend can subscribe to:
-- - incidents: New incidents, status changes, assignments (org-scoped via RLS)
-- - alerts: New incoming alerts (org-scoped via RLS)  
-- - monitors: Service up/down status changes (org-scoped via RLS)
