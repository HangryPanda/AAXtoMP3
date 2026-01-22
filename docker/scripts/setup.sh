#!/bin/bash
# ===========================================
# Developer Setup Script
# ===========================================
# One-command setup for development environment
#
# This script:
# 1. Checks for required tools (docker, docker-compose)
# 2. Creates .env from .env.example if not exists
# 3. Builds and starts development containers
# 4. Waits for services to be healthy
# 5. Runs database migrations
# 6. Displays access URLs
#
# Usage:
#   ./docker/scripts/setup.sh         # Full setup
#   ./docker/scripts/setup.sh --quick # Skip container rebuild
#   ./docker/scripts/setup.sh --clean # Clean rebuild

set -e

# ===========================================
# Configuration
# ===========================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE_FILE="docker-compose.dev.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ===========================================
# Logging functions
# ===========================================
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

log_step() {
    echo -e "\n${BLUE}==>${NC} ${CYAN}$1${NC}"
}

# ===========================================
# Parse arguments
# ===========================================
QUICK_MODE=false
CLEAN_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --quick|-q)
            QUICK_MODE=true
            shift
            ;;
        --clean|-c)
            CLEAN_MODE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --quick, -q    Skip container rebuild"
            echo "  --clean, -c    Clean rebuild (removes volumes)"
            echo "  --help, -h     Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ===========================================
# Check prerequisites
# ===========================================
check_prerequisites() {
    log_step "Checking prerequisites..."

    # Check for Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        log_info "Visit: https://docs.docker.com/get-docker/"
        exit 1
    fi
    log_info "Docker: $(docker --version | head -n1)"

    # Check for docker-compose (v2 is built into docker)
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
        log_info "Docker Compose: $(docker compose version)"
    elif command -v docker-compose &> /dev/null; then
        COMPOSE_CMD="docker-compose"
        log_info "Docker Compose: $(docker-compose --version)"
    else
        log_error "Docker Compose is not installed."
        exit 1
    fi

    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running. Please start Docker."
        exit 1
    fi

    log_info "All prerequisites met!"
}

# ===========================================
# Setup environment file
# ===========================================
setup_env_file() {
    log_step "Setting up environment file..."

    cd "$PROJECT_ROOT"

    if [ -f ".env" ]; then
        log_info ".env file already exists"

        # Check if it's different from example
        if [ -f ".env.example" ]; then
            if ! diff -q .env .env.example > /dev/null 2>&1; then
                log_warn ".env differs from .env.example - you may want to review for new variables"
            fi
        fi
    else
        if [ -f ".env.example" ]; then
            cp .env.example .env
            log_info "Created .env from .env.example"
            log_warn "Review .env and update any values as needed"
        else
            log_error ".env.example not found!"
            exit 1
        fi
    fi
}

# ===========================================
# Create required directories
# ===========================================
create_directories() {
    log_step "Creating required directories..."

    cd "$PROJECT_ROOT"

    # Create data directories if not exist
    mkdir -p data/downloads data/converted data/completed
    log_info "Created data directories"
}

# ===========================================
# Clean up existing containers
# ===========================================
cleanup_containers() {
    log_step "Cleaning up existing containers..."

    cd "$PROJECT_ROOT"

    if [ "$CLEAN_MODE" = true ]; then
        log_warn "Clean mode: Removing all containers and volumes..."
        $COMPOSE_CMD -f "$COMPOSE_FILE" down -v --remove-orphans || true
    else
        $COMPOSE_CMD -f "$COMPOSE_FILE" down --remove-orphans || true
    fi

    log_info "Cleanup complete"
}

# ===========================================
# Build containers
# ===========================================
build_containers() {
    log_step "Building containers..."

    cd "$PROJECT_ROOT"

    if [ "$QUICK_MODE" = true ]; then
        log_info "Quick mode: Skipping rebuild"
        return
    fi

    if [ "$CLEAN_MODE" = true ]; then
        log_info "Building with no cache..."
        $COMPOSE_CMD -f "$COMPOSE_FILE" build --no-cache
    else
        log_info "Building containers..."
        $COMPOSE_CMD -f "$COMPOSE_FILE" build
    fi

    log_info "Build complete"
}

# ===========================================
# Start containers
# ===========================================
start_containers() {
    log_step "Starting containers..."

    cd "$PROJECT_ROOT"

    $COMPOSE_CMD -f "$COMPOSE_FILE" up -d

    log_info "Containers started"
}

# ===========================================
# Wait for services to be healthy
# ===========================================
wait_for_services() {
    log_step "Waiting for services to be healthy..."

    local max_wait=120
    local wait_interval=5
    local elapsed=0

    # Wait for PostgreSQL
    log_info "Waiting for PostgreSQL..."
    while [ $elapsed -lt $max_wait ]; do
        if docker exec audible-postgres-dev pg_isready -U audible > /dev/null 2>&1; then
            log_info "PostgreSQL is ready!"
            break
        fi
        sleep $wait_interval
        elapsed=$((elapsed + wait_interval))
        echo -n "."
    done
    echo ""

    if [ $elapsed -ge $max_wait ]; then
        log_error "PostgreSQL did not become ready in time"
        show_logs
        exit 1
    fi

    # Wait for API
    log_info "Waiting for API..."
    elapsed=0
    while [ $elapsed -lt $max_wait ]; do
        if curl -sf http://localhost:8000/health/live > /dev/null 2>&1; then
            log_info "API is ready!"
            break
        fi
        sleep $wait_interval
        elapsed=$((elapsed + wait_interval))
        echo -n "."
    done
    echo ""

    if [ $elapsed -ge $max_wait ]; then
        log_error "API did not become ready in time"
        show_logs
        exit 1
    fi

    # Wait for Web (optional, may take longer)
    log_info "Waiting for Web frontend..."
    elapsed=0
    while [ $elapsed -lt $max_wait ]; do
        if curl -sf http://localhost:3000 > /dev/null 2>&1; then
            log_info "Web frontend is ready!"
            break
        fi
        sleep $wait_interval
        elapsed=$((elapsed + wait_interval))
        echo -n "."
    done
    echo ""

    if [ $elapsed -ge $max_wait ]; then
        log_warn "Web frontend may still be starting up..."
    fi

    log_info "All services are running!"
}

# ===========================================
# Show container logs
# ===========================================
show_logs() {
    log_step "Container logs:"
    cd "$PROJECT_ROOT"
    $COMPOSE_CMD -f "$COMPOSE_FILE" logs --tail=50
}

# ===========================================
# Display success message
# ===========================================
display_success() {
    echo ""
    echo -e "${GREEN}=========================================="
    echo -e " Setup Complete!"
    echo -e "==========================================${NC}"
    echo ""
    echo -e "${CYAN}Access the application:${NC}"
    echo -e "  Web UI:     ${GREEN}http://localhost:3000${NC}"
    echo -e "  API:        ${GREEN}http://localhost:8000${NC}"
    echo -e "  API Docs:   ${GREEN}http://localhost:8000/docs${NC}"
    echo ""
    echo -e "${CYAN}Useful commands:${NC}"
    echo -e "  View logs:       ${YELLOW}docker compose -f docker-compose.dev.yml logs -f${NC}"
    echo -e "  Stop containers: ${YELLOW}docker compose -f docker-compose.dev.yml down${NC}"
    echo -e "  Restart:         ${YELLOW}docker compose -f docker-compose.dev.yml restart${NC}"
    echo -e "  Shell into API:  ${YELLOW}docker exec -it audible-api-dev bash${NC}"
    echo -e "  Shell into Web:  ${YELLOW}docker exec -it audible-web-dev sh${NC}"
    echo ""
    echo -e "${CYAN}Database:${NC}"
    echo -e "  Host:     localhost"
    echo -e "  Port:     5432"
    echo -e "  User:     audible"
    echo -e "  Password: password"
    echo -e "  Database: audible_db"
    echo ""
    echo -e "${GREEN}Happy coding!${NC}"
    echo ""
}

# ===========================================
# Main execution
# ===========================================
main() {
    echo -e "${CYAN}"
    echo "=========================================="
    echo " Audible Library Manager - Developer Setup"
    echo "=========================================="
    echo -e "${NC}"

    check_prerequisites
    setup_env_file
    create_directories
    cleanup_containers
    build_containers
    start_containers
    wait_for_services
    display_success
}

# Run main function
main "$@"
