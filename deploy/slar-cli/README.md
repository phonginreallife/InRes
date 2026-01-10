# inres CLI

A command-line tool for building and deploying inres services.

## Installation

### Build from source

```bash
cd deploy/inres-cli
go build -o inres .
```

### Add to PATH (optional)

```bash
# Linux/macOS
sudo mv inres /usr/local/bin/

# Or add to your shell profile
export PATH="$PATH:/path/to/inres-cli"
```

## Available Services

| Service | Description |
|---------|-------------|
| `web` | Next.js frontend application |
| `api` | Go API server |
| `ai` | Python AI agent service |
| `slack-worker` | Slack notification worker |

## Commands

### `build`

Build Docker images without pushing to registry.

```bash
inres build [services...] [flags]
```

**Flags:**
- `--registry` - Docker registry (default: `ghcr.io/inresops`)
- `--tag` - Image tag (default: `1.0.1`)
- `--platforms` - Target platforms for multi-architecture builds (comma-separated)

**Examples:**

```bash
# Build all services
inres build

# Build only AI service
inres build ai

# Build multiple specific services
inres build api ai

# Build with custom tag
inres build --tag=2.0.0 web api

# Build for multiple platforms (ARM and AMD)
inres build --platforms=linux/amd64,linux/arm64 api

# Build for ARM only
inres build --platforms=linux/arm64 ai

# Build all services for multiple platforms
inres build --platforms=linux/amd64,linux/arm64,darwin/amd64,darwin/arm64
```

### `push`

Build Docker images and push to registry.

```bash
inres push [services...] [flags]
```

**Flags:**
- `--registry` - Docker registry (default: `ghcr.io/inresops`)
- `--tag` - Image tag (default: `1.0.1`)
- `--platforms` - Target platforms for multi-architecture builds (comma-separated)

**Examples:**

```bash
# Build and push all services
inres push

# Build and push only AI service
inres push ai

# Build and push to custom registry
inres push --registry=myregistry.io/myorg --tag=2.0.0 api ai

# Push only web service with new tag
inres push --tag=1.2.0 web

# Build and push multi-platform images (ARM and AMD)
inres push --platforms=linux/amd64,linux/arm64 api ai

# Build and push all services for ARM64
inres push --platforms=linux/arm64
```

### `migrate`

Run database migrations using Supabase CLI or direct psql.

```bash
inres migrate [flags]
```

**Environment Variables Required:**
- `DATABASE_URL` - PostgreSQL connection string (required)
- `SUPABASE_URL` - Supabase project URL (optional with `--direct`)

**Flags:**
- `--direct` - Use direct psql instead of Supabase CLI
- `--path` - Path to migrations directory (default: auto-detect `supabase/migrations`)
- `--dry-run` - List migrations without applying them

**Examples:**

```bash
# Auto-detect and run migrations
inres migrate

# Use direct psql (skip Supabase CLI)
inres migrate --direct

# Custom migrations path
inres migrate --path=./custom/migrations

# Preview migrations without applying
inres migrate --dry-run
```

**Migration Strategy:**

1. The CLI first validates `DATABASE_URL` and `SUPABASE_URL` environment variables
2. If `--direct` is not specified, it attempts to use Supabase CLI:
   - Extracts project reference from `SUPABASE_URL`
   - Links to Supabase project
   - Runs `supabase db push`
3. If Supabase CLI fails or `--direct` is specified, falls back to direct psql:
   - Applies each `.sql` file in order using `psql`

## Workflow

The CLI performs the following steps:

### For `build`:
1. Check environment (.env file)
2. Fix line endings in scripts
3. Build Next.js (only if `web` is selected)
4. Build Docker images using docker-compose
5. Tag images with registry and version

### For `push`:
1. All steps from `build`
2. Push tagged images to registry

### For `migrate`:
1. Validate environment variables (`DATABASE_URL`, `SUPABASE_URL`)
2. Auto-detect or use specified migrations directory
3. Find and sort all `.sql` migration files
4. Apply migrations via Supabase CLI or direct psql

## Directory Structure

The CLI expects to be run from the `deploy/inres-cli` directory with the following structure:

```
inres-oss/
├── api/
│   └── ai/
│       └── docker-entrypoint.sh
├── web/
│   └── inres/
│       └── package.json
├── supabase/
│   └── migrations/
│       └── *.sql
└── deploy/
    ├── docker/
    │   └── docker-compose.yaml
    └── inres-cli/
        ├── main.go
        ├── cmd/
        │   ├── root.go
        │   ├── push.go
        │   └── migrate.go
        └── inres (binary)
```

## Prerequisites

- Go 1.21+ (for building)
- Docker with Compose v2
- Node.js and npm (for web service)
- Access to target Docker registry (for push)
- Docker Buildx (for multi-platform builds)
- PostgreSQL client (`psql`) (for migrate with `--direct`)
- Supabase CLI (for migrate without `--direct`)

## Multi-Platform Builds

The CLI supports building Docker images for multiple architectures using Docker Buildx. This is useful for deploying to different platforms like ARM-based servers (AWS Graviton, Raspberry Pi) and AMD64 servers.

### Supported Platforms

- `linux/amd64` - Standard x86_64 Linux (most common)
- `linux/arm64` - ARM64 Linux (AWS Graviton, Apple Silicon, Raspberry Pi)
- `darwin/amd64` - Intel-based macOS
- `darwin/arm64` - Apple Silicon macOS

### How It Works

When you specify the `--platforms` flag:

1. The CLI automatically creates a Docker Buildx builder if needed
2. For single-platform builds, images are loaded into your local Docker daemon
3. For multi-platform builds, images are automatically pushed to the registry (required by Docker Buildx)

**Important Notes:**

- Multi-platform builds require pushing to a registry (you cannot load multi-platform images locally)
- Ensure you're authenticated to the registry before running multi-platform builds
- The first multi-platform build may take longer as it sets up QEMU emulation

### Example Workflows

```bash
# Local development (single platform)
inres build --platforms=linux/amd64 api

# Deploy to ARM and AMD servers
inres push --platforms=linux/amd64,linux/arm64 --tag=v1.2.3

# Build for Apple Silicon
inres build --platforms=darwin/arm64 web
```

## Authentication

Before pushing to a registry, ensure you're authenticated:

```bash
# GitHub Container Registry
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Docker Hub
docker login

# Custom registry
docker login myregistry.io
```

## Troubleshooting

### "Next.js build failed: .next/standalone not found"

Ensure your `next.config.js` has output set to standalone:

```js
module.exports = {
  output: 'standalone',
}
```

### "Unknown service" warning

Check that the service name matches one of: `web`, `api`, `ai`, `slack-worker`

### Docker build fails

1. Ensure Docker daemon is running
2. Check docker-compose.yaml exists in `deploy/docker/`
3. Verify sufficient disk space for images

### Migration fails with "psql: command not found"

Install PostgreSQL client:

```bash
# macOS
brew install postgresql

# Ubuntu/Debian
sudo apt-get install postgresql-client

# Alpine
apk add postgresql-client
```

### Migration fails with "supabase: command not found"

Install Supabase CLI:

```bash
# macOS
brew install supabase/tap/supabase

# npm
npm install -g supabase

# Or use --direct flag to bypass Supabase CLI
inres migrate --direct
```

### Migration fails with "Could not extract project reference"

This happens when `SUPABASE_URL` is not in the expected format (`https://xxx.supabase.co`). For self-hosted Supabase, use the `--direct` flag.

## License

Part of the inres project.
