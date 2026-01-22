#!/bin/bash
# ===========================================
# Web Frontend Entrypoint Script
# ===========================================
# This script handles:
# 1. Waiting for the API to be ready (optional)
# 2. Starting the Next.js application
#
# Environment variables:
#   NEXT_PUBLIC_API_URL: Backend API URL (required for API health check)
#   PORT: Port to listen on (default: 3000)
#   NODE_ENV: Node environment (default: production)
#   WAIT_FOR_API: Wait for API to be ready (default: false)
#   HOSTNAME: Hostname to bind to (default: 0.0.0.0)

set -e

# ===========================================
# Configuration
# ===========================================
PORT="${PORT:-3000}"
NODE_ENV="${NODE_ENV:-production}"
WAIT_FOR_API="${WAIT_FOR_API:-false}"
HOSTNAME="${HOSTNAME:-0.0.0.0}"
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
# Wait for API to be ready
# ===========================================
wait_for_api() {
    if [ "$WAIT_FOR_API" != "true" ]; then
        log_info "Skipping API health check (WAIT_FOR_API is not true)"
        return 0
    fi

    if [ -z "$NEXT_PUBLIC_API_URL" ]; then
        log_warn "NEXT_PUBLIC_API_URL not set, skipping API health check"
        return 0
    fi

    log_info "Waiting for API to be ready at ${NEXT_PUBLIC_API_URL}..."

    local retries=0
    local health_url="${NEXT_PUBLIC_API_URL}/health/live"

    while [ $retries -lt $MAX_RETRIES ]; do
        # Try to reach the API health endpoint
        if command -v curl &> /dev/null; then
            if curl -sf "$health_url" > /dev/null 2>&1; then
                log_info "API is ready!"
                return 0
            fi
        elif command -v wget &> /dev/null; then
            if wget -q --spider "$health_url" 2>/dev/null; then
                log_info "API is ready!"
                return 0
            fi
        else
            log_warn "Neither curl nor wget available, skipping API check"
            return 0
        fi

        retries=$((retries + 1))
        log_info "API not ready yet (attempt $retries/$MAX_RETRIES). Retrying in ${RETRY_INTERVAL}s..."
        sleep $RETRY_INTERVAL
    done

    log_warn "API did not become ready in time, starting anyway..."
    return 0
}

# ===========================================
# Start the application
# ===========================================
start_application() {
    log_info "Starting Next.js application..."
    log_info "Environment: ${NODE_ENV}"
    log_info "Port: ${PORT}"
    log_info "Hostname: ${HOSTNAME}"

    if [ "$NODE_ENV" = "production" ]; then
        # Production mode - use standalone server
        if [ -f "server.js" ]; then
            log_info "Starting standalone Next.js server..."
            exec node server.js
        else
            log_info "Starting Next.js with npm start..."
            exec npm run start
        fi
    else
        # Development mode - use next dev
        log_info "Starting Next.js in development mode..."
        exec npm run dev
    fi
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
    log_info "Audible Library Manager Web Entrypoint"
    log_info "=========================================="

    wait_for_api
    start_application
}

main "$@"
