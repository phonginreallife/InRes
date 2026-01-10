-- Step 1: Create user record in app database
INSERT INTO users (id, name, email, role, team, is_active, created_at, updated_at, provider_id)
VALUES (
    'bdc208a3-3133-4f22-9c5a-00160a99780a',
    'Test User B',
    'testuser@companyb.com',
    'engineer',
    'testing',
    true,
    NOW(),
    NOW(),
    'bdc208a3-3133-4f22-9c5a-00160a99780a'
);

-- Step 2: Add user as owner of Test Company B
INSERT INTO memberships (user_id, resource_type, resource_id, role, created_at, updated_at)
VALUES (
    'bdc208a3-3133-4f22-9c5a-00160a99780a',
    'org',
    '7a9ae2f1-e17a-4dea-9c30-42fc606d55b5',
    'owner',
    NOW(),
    NOW()
);

-- Step 3: Verify it worked
SELECT 
    u.name as user_name, 
    u.email,
    m.role,
    o.name as org_name
FROM memberships m
JOIN users u ON m.user_id = u.id
LEFT JOIN organizations o ON m.resource_id = o.id 
WHERE m.resource_type = 'org'
ORDER BY o.name;