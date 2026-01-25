#!/bin/bash
# ===========================================
# NFS Stale File Cleanup Script
# ===========================================
# This script finds and removes stale .nfs* files that can be left behind
# when Docker containers are stopped while processes have NFS-mounted files open.
#
# Usage:
#   ./cleanup-nfs-files.sh [--dry-run] [--age DAYS] [DIRECTORIES...]
#
# Options:
#   --dry-run    Show what would be deleted without actually deleting
#   --age DAYS   Only delete files older than DAYS (default: 1)
#
# Examples:
#   ./cleanup-nfs-files.sh                              # Clean default directories
#   ./cleanup-nfs-files.sh --dry-run                    # Preview what would be deleted
#   ./cleanup-nfs-files.sh --age 0 /path/to/dir         # Clean files of any age in specific dir
#   ./cleanup-nfs-files.sh /mnt/nfs/data /mnt/nfs/logs  # Clean specific directories
#
# Cron job example (run daily at 3am):
#   0 3 * * * /path/to/cleanup-nfs-files.sh >> /var/log/nfs-cleanup.log 2>&1
#
# ===========================================

set -e

# Default settings
DRY_RUN=false
AGE_DAYS=1
DIRECTORIES=()

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

log_dry() {
    echo -e "${BLUE}[DRY-RUN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# ===========================================
# Usage
# ===========================================
usage() {
    echo "Usage: $0 [--dry-run] [--age DAYS] [DIRECTORIES...]"
    echo ""
    echo "Options:"
    echo "  --dry-run    Show what would be deleted without actually deleting"
    echo "  --age DAYS   Only delete files older than DAYS (default: 1)"
    echo "  --help       Show this help message"
    echo ""
    echo "If no directories are specified, uses default NFS mount paths."
    exit 1
}

# ===========================================
# Parse arguments
# ===========================================
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --age)
            AGE_DAYS="$2"
            shift 2
            ;;
        --help|-h)
            usage
            ;;
        -*)
            log_error "Unknown option: $1"
            usage
            ;;
        *)
            DIRECTORIES+=("$1")
            shift
            ;;
    esac
done

# ===========================================
# Default directories if none specified
# ===========================================
if [ ${#DIRECTORIES[@]} -eq 0 ]; then
    # Add common NFS mount points - adjust these for your environment
    DEFAULT_DIRS=(
        "/Volumes/Media/Audiobooks/Downloads"
        "/Volumes/Media/Audiobooks/Converted"
        "/Volumes/Media/Audiobooks/Completed"
        "/data/downloads"
        "/data/converted"
        "/data/completed"
    )

    for dir in "${DEFAULT_DIRS[@]}"; do
        if [ -d "$dir" ]; then
            DIRECTORIES+=("$dir")
        fi
    done
fi

if [ ${#DIRECTORIES[@]} -eq 0 ]; then
    log_error "No valid directories found to clean"
    exit 1
fi

# ===========================================
# Main cleanup logic
# ===========================================
log_info "=========================================="
log_info "NFS Stale File Cleanup"
log_info "=========================================="
log_info "Mode: $([ "$DRY_RUN" = true ] && echo 'DRY RUN' || echo 'LIVE')"
log_info "Age threshold: ${AGE_DAYS} day(s)"
log_info "Directories: ${DIRECTORIES[*]}"
log_info "=========================================="

total_found=0
total_deleted=0
total_size=0

for dir in "${DIRECTORIES[@]}"; do
    if [ ! -d "$dir" ]; then
        log_warn "Directory does not exist: $dir"
        continue
    fi

    log_info "Scanning: $dir"

    # Find .nfs* files older than AGE_DAYS
    # Using -mtime +N means "more than N days ago"
    # -mtime 0 means "within the last 24 hours"
    # -mtime +0 means "more than 24 hours ago"

    if [ "$AGE_DAYS" -eq 0 ]; then
        # Find all .nfs* files regardless of age
        find_args=("$dir" -name ".nfs*" -type f)
    else
        # Find .nfs* files older than AGE_DAYS
        find_args=("$dir" -name ".nfs*" -type f -mtime +"$((AGE_DAYS - 1))")
    fi

    # Process each file found
    while IFS= read -r -d '' file; do
        if [ -z "$file" ]; then
            continue
        fi

        total_found=$((total_found + 1))

        # Get file size
        if command -v stat &> /dev/null; then
            # macOS stat
            if [[ "$OSTYPE" == "darwin"* ]]; then
                file_size=$(stat -f%z "$file" 2>/dev/null || echo 0)
            else
                # Linux stat
                file_size=$(stat -c%s "$file" 2>/dev/null || echo 0)
            fi
        else
            file_size=0
        fi

        total_size=$((total_size + file_size))

        # Get file age
        if [[ "$OSTYPE" == "darwin"* ]]; then
            file_date=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M" "$file" 2>/dev/null || echo "unknown")
        else
            file_date=$(stat -c "%y" "$file" 2>/dev/null | cut -d'.' -f1 || echo "unknown")
        fi

        if [ "$DRY_RUN" = true ]; then
            log_dry "Would delete: $file (size: $file_size bytes, modified: $file_date)"
        else
            if rm -f "$file" 2>/dev/null; then
                log_info "Deleted: $file (size: $file_size bytes, modified: $file_date)"
                total_deleted=$((total_deleted + 1))
            else
                log_warn "Failed to delete: $file"
            fi
        fi
    done < <(find "${find_args[@]}" -print0 2>/dev/null)
done

# ===========================================
# Summary
# ===========================================
log_info "=========================================="
log_info "Cleanup Summary"
log_info "=========================================="
log_info "Total .nfs* files found: $total_found"

# Convert size to human-readable
if [ $total_size -gt 1073741824 ]; then
    size_human="$(echo "scale=2; $total_size / 1073741824" | bc) GB"
elif [ $total_size -gt 1048576 ]; then
    size_human="$(echo "scale=2; $total_size / 1048576" | bc) MB"
elif [ $total_size -gt 1024 ]; then
    size_human="$(echo "scale=2; $total_size / 1024" | bc) KB"
else
    size_human="$total_size bytes"
fi

log_info "Total size: $size_human"

if [ "$DRY_RUN" = true ]; then
    log_dry "Files that would be deleted: $total_found"
else
    log_info "Files deleted: $total_deleted"
    if [ $total_found -ne $total_deleted ]; then
        log_warn "Some files could not be deleted"
    fi
fi

log_info "=========================================="

exit 0
