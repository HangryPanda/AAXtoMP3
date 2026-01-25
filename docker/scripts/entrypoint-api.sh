#!/bin/bash
# ===========================================
# API Entrypoint Script
# ===========================================
# This script handles:
# 1. Waiting for PostgreSQL to be ready
# 2. Running database migrations
# 3. Starting the uvicorn server
#
# Environment variables:
#   DATABASE_URL: PostgreSQL connection string (required)
#   API_HOST: Host to bind to (default: 0.0.0.0)
#   API_PORT: Port to listen on (default: 8000)
#   DEBUG: Enable debug mode (default: false)
#   WORKERS: Number of uvicorn workers (default: 1)
#   SKIP_MIGRATIONS: Skip running migrations (default: false)

set -e

# ===========================================
# Configuration
# ===========================================
API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-8000}"
DEBUG="${DEBUG:-false}"
WORKERS="${WORKERS:-1}"
SKIP_MIGRATIONS="${SKIP_MIGRATIONS:-false}"
MAX_RETRIES="${MAX_RETRIES:-30}"
RETRY_INTERVAL="${RETRY_INTERVAL:-2}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ===========================================
# Logging functions
# ===========================================
log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" >&2
}

# ===========================================
# Extract database connection info from URL
# ===========================================
parse_database_url() {
    if [ -z "$DATABASE_URL" ]; then
        log_error "DATABASE_URL environment variable is not set"
        exit 1
    fi

    # Extract host and port from DATABASE_URL
    # Format: postgresql+asyncpg://user:pass@host:port/dbname
    DB_HOST=$(echo "$DATABASE_URL" | sed -E 's|.*@([^:]+):([0-9]+)/.*|\1|')
    DB_PORT=$(echo "$DATABASE_URL" | sed -E 's|.*@([^:]+):([0-9]+)/.*|\2|')

    if [ -z "$DB_HOST" ] || [ -z "$DB_PORT" ]; then
        log_error "Failed to parse DATABASE_URL"
        exit 1
    fi

    log_info "Database host: $DB_HOST, port: $DB_PORT"
}

# ===========================================
# Wait for PostgreSQL to be ready
# ===========================================
wait_for_postgres() {
    log_info "Waiting for PostgreSQL to be ready..."

    local retries=0
    while [ $retries -lt $MAX_RETRIES ]; do
        # Try to connect using pg_isready if available, otherwise use Python
        if command -v pg_isready &> /dev/null; then
            if pg_isready -h "$DB_HOST" -p "$DB_PORT" -q; then
                log_info "PostgreSQL is ready!"
                return 0
            fi
        else
            # Fallback: Use Python to check connection
            if python -c "
import socket
import sys
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    result = sock.connect_ex(('$DB_HOST', $DB_PORT))
    sock.close()
    sys.exit(0 if result == 0 else 1)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
                log_info "PostgreSQL is ready!"
                return 0
            fi
        fi

        retries=$((retries + 1))
        log_info "PostgreSQL not ready yet (attempt $retries/$MAX_RETRIES). Retrying in ${RETRY_INTERVAL}s..."
        sleep $RETRY_INTERVAL
    done

    log_error "PostgreSQL did not become ready in time"
    exit 1
}

# ===========================================
# Run database migrations
# ===========================================
run_migrations() {
    if [ "$SKIP_MIGRATIONS" = "true" ]; then
        log_warn "Skipping database migrations (SKIP_MIGRATIONS=true)"
        return 0
    fi

    log_info "Running database migrations..."

    # Check if alembic.ini exists
    if [ ! -f "alembic.ini" ]; then
        log_error "alembic.ini not found. Cannot run migrations."
        exit 1
    fi

    # Run migrations with retry logic
    local retries=0
    local max_migration_retries=3

    while [ $retries -lt $max_migration_retries ]; do
        if alembic upgrade head; then
            log_info "Database migrations completed successfully!"
            return 0
        fi

        retries=$((retries + 1))
        if [ $retries -lt $max_migration_retries ]; then
            log_warn "Migration failed (attempt $retries/$max_migration_retries). Retrying..."
            sleep 2
        fi
    done

    log_error "Failed to run database migrations after $max_migration_retries attempts"
    exit 1
}

# ===========================================
# Verify required directories
# ===========================================
verify_directories() {
    log_info "Verifying required directories..."

    local dirs=("/data/downloads" "/data/converted" "/data/completed")

    for dir in "${dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            log_info "Creating directory: $dir"
            mkdir -p "$dir" 2>/dev/null || log_warn "Could not create $dir (may already exist or permission issue)"
        fi
    done

    log_info "Directory verification complete"
}

# ===========================================
# Start the application
# ===========================================
start_application() {
    log_info "Starting Audible Library Manager API..."

    # Build uvicorn command
    local uvicorn_args=("uvicorn" "main:app" "--host" "$API_HOST" "--port" "$API_PORT")

    if [ "$DEBUG" = "true" ]; then
        log_info "Debug mode enabled - using --reload with polling (macOS compatible)"
        uvicorn_args+=("--reload" "--reload-dir" "/app")
    else
        log_info "Production mode - using $WORKERS worker(s)"
        uvicorn_args+=("--workers" "$WORKERS")
    fi

    log_info "Starting uvicorn with: ${uvicorn_args[*]}"
    exec "${uvicorn_args[@]}"
}

# ===========================================
# Signal handlers
# ===========================================
cleanup() {
    log_info "Received shutdown signal, cleaning up..."
    exit 0
}

trap cleanup SIGTERM SIGINT

# ===========================================
# Main execution
# ===========================================
main() {
    log_info "=========================================="
    log_info "Audible Library Manager API Entrypoint"
    log_info "=========================================="

    parse_database_url
    wait_for_postgres
    verify_directories
    run_migrations
    start_application
}

main "$@"
