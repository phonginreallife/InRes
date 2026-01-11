-- Add more integration types to the integrations table
-- Current: prometheus, datadog, grafana, webhook, aws, custom
-- Adding: pagerduty, coralogix, opsgenie, victorops, slack, email, sms, teams

-- Drop the existing constraint
ALTER TABLE integrations DROP CONSTRAINT IF EXISTS integrations_type_valid;

-- Add the new constraint with more types
ALTER TABLE integrations ADD CONSTRAINT integrations_type_valid CHECK (
    type::text = ANY (ARRAY[
        'prometheus',
        'datadog', 
        'grafana',
        'webhook',
        'aws',
        'custom',
        'pagerduty',
        'coralogix',
        'opsgenie',
        'victorops',
        'slack',
        'email',
        'sms',
        'teams',
        'jira',
        'servicenow',
        'zendesk'
    ]::text[])
);

COMMENT ON CONSTRAINT integrations_type_valid ON integrations IS 'Validates integration type against supported providers';
