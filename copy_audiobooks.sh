#!/bin/bash
# copy_audiobooks.sh
#
# This script copies the contents of
# /Users/jasonvongsay/codespace/AAXtoMP3/Audiobook
# to /Users/jasonvongsay/Entertainment_NAS/Audiobooks,
# providing status updates and real-time progress.
#
# It first checks if the destination folder exists and if its total size 
# matches the source. If they match, the transfer is skipped.
# Otherwise, it overwrites the destination.
#
# Optimizations:
#   - Uses --whole-file (-W) to bypass the delta algorithm for faster local transfers.
#   - Uses --info=progress2 for an overall detailed progress update.

SOURCE="/Users/jasonvongsay/codespace/AAXtoMP3/Audiobook/"
DESTINATION="/Users/jasonvongsay/Entertainment_NAS/Audiobooks/"

echo "========================================"
echo "Starting file transfer..."
echo "Source:      $SOURCE"
echo "Destination: $DESTINATION"
echo "========================================"
echo ""

# Create destination directory if it doesn't exist.
if [ ! -d "$DESTINATION" ]; then
    echo "Destination directory doesn't exist. Creating it..."
    mkdir -p "$DESTINATION"
fi

# If the destination folder exists, compare the total sizes.
if [ -d "$DESTINATION" ]; then
    echo "Checking folder sizes..."
    SOURCE_SIZE=$(du -sk "$SOURCE" | awk '{print $1}')
    DEST_SIZE=$(du -sk "$DESTINATION" | awk '{print $1}')
    echo "Source size:      $SOURCE_SIZE KB"
    echo "Destination size: $DEST_SIZE KB"
    
    if [ "$SOURCE_SIZE" -eq "$DEST_SIZE" ]; then
        echo "The destination folder is the same size as the source."
        echo "Skipping file transfer."
        exit 0
    else
        echo "Sizes differ. Overwriting the destination folder with source files..."
    fi
fi

echo ""
echo "Transferring files. This may take a while..."
echo ""

# Run rsync with:
# -a : Archive mode (recursively copy files, preserve permissions, timestamps, etc.)
# -v : Verbose output
# -h : Human-readable numbers (file sizes)
# -P : Shows progress for each file and allows partial transfers
# -W : Use whole-file mode (disables delta algorithm, which speeds up transfers locally)
# --info=progress2 : Provides overall progress information
/opt/homebrew/bin/rsync -avhPW --info=progress2 --no-group --no-owner "$SOURCE" "$DESTINATION"
RSYNC_EXIT=$?

if [ $RSYNC_EXIT -ne 0 ]; then
    echo "----------------------------------------"
    echo "Rsync encountered an error (exit code $RSYNC_EXIT)."
    echo "Please check the above output for details."
    exit $RSYNC_EXIT
else
    echo "----------------------------------------"
    echo "Rsync completed successfully."
fi