import os
import shutil
from pathlib import Path

# Configuration
SOURCE_AUDIO_DIR = Path("M4B")  # Your local M4B folder
TARGET_BASE_DIR = Path("/Volumes/Media/Audiobooks/Converted/Audiobook")

def consolidate():
    if not SOURCE_AUDIO_DIR.exists():
        print(f"Error: Source directory '{SOURCE_AUDIO_DIR}' not found.")
        return

    if not TARGET_BASE_DIR.exists():
        print(f"Error: Target directory '{TARGET_BASE_DIR}' not found.")
        return

    print(f"Scanning {SOURCE_AUDIO_DIR}...")
    
    count = 0
    # Walk the source M4B directory
    for root, dirs, files in os.walk(SOURCE_AUDIO_DIR):
        for file in files:
            if file.lower().endswith(".m4b"):
                source_path = Path(root) / file
                
                # Calculate relative path to preserve structure (e.g., "Author/Title/Book.m4b")
                rel_path = source_path.relative_to(SOURCE_AUDIO_DIR)
                dest_path = TARGET_BASE_DIR / rel_path
                
                # Skip if already exists
                if dest_path.exists():
                    print(f"Skipping (exists): {rel_path}")
                    continue
                
                # Ensure destination folder exists
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                
                print(f"Copying: {rel_path}")
                try:
                    shutil.copy2(source_path, dest_path)
                    count += 1
                except Exception as e:
                    print(f"Failed to copy {source_path}: {e}")

    print(f"\nConsolidation complete. Copied {count} files.")

if __name__ == "__main__":
    consolidate()
