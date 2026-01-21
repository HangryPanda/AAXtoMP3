import os
import json
import subprocess
import time
import argparse
import sys
from datetime import datetime, timedelta

# Define paths
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))  # Local audiobook directory
LIBRARY_DATA_DIR = os.path.join(ROOT_DIR, "LibraryData")
TMP_DIR = os.path.join(ROOT_DIR, "tmp")  # Temp folder

# Ensure necessary directories exist
os.makedirs(LIBRARY_DATA_DIR, exist_ok=True)
os.makedirs(TMP_DIR, exist_ok=True)

# Define JSON file paths
MISSING_FILE = os.path.join(LIBRARY_DATA_DIR, "missing_audiobooks.json")
LOCAL_LIBRARY_FILE = os.path.join(LIBRARY_DATA_DIR, "local_library.json")
AUDIBLE_LIBRARY_FILE = os.path.join(LIBRARY_DATA_DIR, "audible_library.json")
MASTER_LIBRARY_FILE = os.path.join(LIBRARY_DATA_DIR, "library.json")
MOVED_FILES_LOG = os.path.join(LIBRARY_DATA_DIR, "moved_files.json")
AUTH_FILE = os.path.expanduser("~/.audible/audibleAuth")

# Define storage directories
AAX_DIR = os.path.join(ROOT_DIR, "AAX")
M4B_DIR = os.path.join(ROOT_DIR, "M4B")
MP3_DIR = os.path.join(ROOT_DIR, "MP3")
COVERS_DIR = os.path.join(ROOT_DIR, "Covers")
METADATA_DIR = os.path.join(ROOT_DIR, "Metadata")
VOUCHERS_DIR = os.path.join(ROOT_DIR, "Vouchers")
CHAPTERS_DIR = os.path.join(ROOT_DIR, "Chapters")

# Ensure necessary directories exist
for directory in [AAX_DIR, M4B_DIR, MP3_DIR, COVERS_DIR, METADATA_DIR, VOUCHERS_DIR, CHAPTERS_DIR]:
    os.makedirs(directory, exist_ok=True)

# 🛠 Move downloaded files from tmp/ to their correct directories
def move_downloaded_files():
    print("🚀 Moving downloaded files from tmp/ to their correct locations...")

    # Load existing log
    moved_files = []
    if os.path.exists(MOVED_FILES_LOG):
        with open(MOVED_FILES_LOG, "r", encoding="utf-8") as log_file:
            try:
                moved_files = json.load(log_file)
            except json.JSONDecodeError:
                pass  # Ignore if file is corrupted

    cutoff_date = datetime.now() - timedelta(days=7)
    moved_files = [entry for entry in moved_files if datetime.strptime(entry["timestamp"], "%Y-%m-%d %H:%M:%S") > cutoff_date]

    for file in os.listdir(TMP_DIR):
        file_path = os.path.join(TMP_DIR, file)
        if os.path.isfile(file_path):
            if file.endswith((".aaxc", ".aax")):
                destination = AAX_DIR
            elif file.endswith(".jpg"):
                destination = COVERS_DIR
            elif file.endswith(".voucher"):
                destination = VOUCHERS_DIR
            elif file.endswith("-chapters.json"):
                destination = CHAPTERS_DIR
            else:
                continue  # Skip unrecognized files

            new_path = os.path.join(destination, file)
            if not os.path.exists(new_path):
                os.rename(file_path, new_path)
                moved_files.append({"file": file, "from": file_path, "to": new_path, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
                print(f"✅ Moved: {file} → {destination}")

    # Save updated move log
    with open(MOVED_FILES_LOG, "w", encoding="utf-8") as log_file:
        json.dump(moved_files, log_file, indent=4)

    print("🎧 File organization complete!")
    cleanup_tmp()

# 🧹 Cleanup tmp folder after processing files
def cleanup_tmp():
    if not os.listdir(TMP_DIR):  # If tmp folder is empty
        os.rmdir(TMP_DIR)
        os.makedirs(TMP_DIR, exist_ok=True)
        print("✅ tmp folder cleaned.")
    else:
        print("⚠️ tmp folder not empty. Some files may not have been processed.")

# 📖 Load local audiobook library JSON
def load_local_library():
    if os.path.exists(LOCAL_LIBRARY_FILE):
        with open(LOCAL_LIBRARY_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return []

# 📖 Create master library by merging local and Audible data
def create_master_library():
    print("📖 Creating master library file...")
    local_library = load_local_library()

    if os.path.exists(AUDIBLE_LIBRARY_FILE):
        with open(AUDIBLE_LIBRARY_FILE, "r", encoding="utf-8") as file:
            audible_library = json.load(file)
    else:
        audible_library = []

    audible_metadata = {book["title"]: book for book in audible_library}

    master_library = []
    for book in local_library:
        title = book.get("title")
        author = book.get("author")
        voucher_file = os.path.join(VOUCHERS_DIR, f"{title.replace(' ', '_')}.voucher")
        voucher_data = {}
        if os.path.exists(voucher_file):
            with open(voucher_file, "r", encoding="utf-8") as vf:
                voucher_data = json.load(vf)

        converted_m4b = None
        if author and title:
            m4b_dir = os.path.join(M4B_DIR, author, title)
            if os.path.exists(m4b_dir):
                for file in os.listdir(m4b_dir):
                    if file.endswith(".m4b"):
                        converted_m4b = os.path.join(m4b_dir, file)
                        break

        master_library.append({
            "title": title,
            "author": author,
            "asin": book.get("asin"),
            "description": book.get("description"),
            "status": book.get("status", "pending"),
            "original_file": book.get("file"),
            "converted_m4b": converted_m4b,
            "converted_mp3": book.get("converted_mp3"),
            "cover": book.get("cover"),
            "chapters": book.get("chapters"),
            "voucher": voucher_file,
            "content_license": voucher_data.get("content_license", {}),
            "response_groups": voucher_data.get("response_groups", []),
            "added_on": datetime.now().strftime("%Y-%m-%d"),
            "last_modified": datetime.now().strftime("%Y-%m-%d")
        })

    master_library.sort(key=lambda x: x["title"].lower())

    with open(MASTER_LIBRARY_FILE, "w", encoding="utf-8") as json_file:
        json.dump({"library": master_library}, json_file, indent=4)

    print(f"✅ Master library JSON saved: {MASTER_LIBRARY_FILE}")

# 🔍 Fetch Audible library
def fetch_audible_library():
    print("🔍 Fetching Audible library...")
    try:
        result = subprocess.run(
            ["audible", "library", "export", "--output", AUDIBLE_LIBRARY_FILE, "--format", "json"],
            capture_output=True, text=True, check=True
        )
        with open(AUDIBLE_LIBRARY_FILE, "w", encoding="utf-8") as json_file:
            json.dump(json.loads(result.stdout), json_file, indent=4)
        print(f"✅ Audible library JSON saved: {AUDIBLE_LIBRARY_FILE}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error fetching Audible library: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error decoding JSON: {e}")
        sys.exit(1)

# 🎧 Interactive CLI
def interactive_cli(local_only):
    print("\n🔹 Audible Library Sync CLI 🔹")
    move_downloaded_files()

    if local_only:
        create_master_library()
        print("\n🎧 Local library update complete! Exiting...")
        sys.exit(0)

    fetch_audible_library()
    create_master_library()
    print("\n🎧 Library sync complete!")

# 📥 Command-line argument parsing
def main():
    parser = argparse.ArgumentParser(description="Sync Audible library and local audiobook collection.")
    parser.add_argument("--local-only", action="store_true", help="Update only the local audiobook library without fetching from Audible.")
    args = parser.parse_args()
    interactive_cli(args.local_only)

# Load missing audiobooks from previous run if it exists
def load_missing_audiobooks():
    if os.path.exists(MISSING_FILE):
        with open(MISSING_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return None

# Save missing audiobooks list to JSON
def save_missing_audiobooks(missing_list):
    with open(MISSING_FILE, "w", encoding="utf-8") as file:
        json.dump(missing_list, file, indent=4)

# Determine missing audiobooks
def find_missing_audiobooks():
    local_library = load_local_library()
    local_titles = {book["title"] for book in local_library}

    audible_library = fetch_audible_library()
    audible_titles = {book["title"] for book in audible_library if book.get("status") == "Active"}

    missing_titles = audible_titles - local_titles

    if not missing_titles:
        print("🎉 All Audible audiobooks are already in your local library.")
        return []

    missing_list = []
    for book in audible_library:
        if book["title"] in missing_titles:
            missing_list.append({
                "title": book["title"],
                "asin": book["asin"],
                "downloaded": False,  # Track if download was successful
                "last_attempt": None  # Timestamp for last download attempt
            })

    return missing_list

# Download audiobooks with fallback cover-size handling
def download_selected_audiobooks(selected_books, missing_list):
    for book in missing_list:
        if book["title"] not in selected_books:
            continue

        if book["downloaded"]:
            print(f"✅ Already downloaded: {book['title']} (Skipping)")
            continue

        asin = book["asin"]
        print(f"⬇️ Downloading: {book['title']} ({asin})...")

        cover_sizes = [1215, 960, 680, 300]  # Fallback cover sizes
        success = False  # Track if download was successful

        for size in cover_sizes:
            try:
                download_cmd = [
                    "audible", "download",
                    "--asin", asin,
                    "--aaxc",
                    "--cover",
                    f"--cover-size={size}",
                    "--chapter",
                    "--output-directory", TMP_DIR  # ✅ Save to tmp/ instead of ROOT_DIR
                ]
                subprocess.run(download_cmd, check=True)
                
                # Mark as downloaded
                book["downloaded"] = True
                book["last_attempt"] = time.strftime("%Y-%m-%d %H:%M:%S")
                save_missing_audiobooks(missing_list)

                print(f"✅ Downloaded: {book['title']} (Cover Size: {size})")
                success = True
                break  # Stop trying once a valid size is found

            except subprocess.CalledProcessError as e:
                print(f"⚠️ Cover size {size} failed for {book['title']}, trying next available size...")

        if not success:
            print(f"❌ Failed to download {book['title']}.")
            continue  # Skip moving files if the download failed

        # Move downloaded files from tmp/ to correct folders
        move_downloaded_files()

    # If all books are downloaded, remove the missing audiobooks file
    if all(book["downloaded"] for book in missing_list):
        print("🎉 All missing audiobooks have been downloaded. Removing tracking file.")
        os.remove(MISSING_FILE)

# Interactive CLI for missing audiobooks
def interactive_missing_audiobooks_cli():
    print("\n🔹 Audible Library Sync CLI 🔹")
    
    # Check for existing missing list
    if os.path.exists(MISSING_FILE):
        overwrite = input("A missing audiobooks list already exists. Overwrite it? (Y/N): ").strip().lower()
        if overwrite in ["y", "yes"]:
            print("📝 Creating a new missing audiobooks list...")
            missing_list = find_missing_audiobooks()
            save_missing_audiobooks(missing_list)
        else:
            print("✅ Using existing missing audiobooks list.")
            missing_list = load_missing_audiobooks()
    else:
        print("📝 Creating a new missing audiobooks list...")
        missing_list = find_missing_audiobooks()
        save_missing_audiobooks(missing_list)

    if not missing_list:
        print("🎉 No missing audiobooks. Exiting...")
        return

    # Print missing audiobooks if requested
    print_missing = input("Would you like to print the missing audiobooks? (Y/N): ").strip().lower()
    if print_missing in ["y", "yes"]:
        print("\n📌 Missing Audiobooks:")
        for idx, book in enumerate(missing_list):
            print(f"[{idx}] {book['title']}")

    # Download selection
    print("\n📥 Download Options:")
    print("1. Download all missing audiobooks")
    print("2. Download specific audiobooks by index or title (comma-separated)")
    choice = input("Enter your choice (1 or 2): ").strip()

    if choice == "1":
        print("⬇️ Downloading all missing audiobooks...")
        download_selected_audiobooks([book["title"] for book in missing_list], missing_list)
    elif choice == "2":
        selected_input = input("Enter the index or title of the books to download (comma-separated): ").strip()
        selected_books = set()
        for item in selected_input.split(","):
            item = item.strip()
            if item.isdigit():
                index = int(item)
                if 0 <= index < len(missing_list):
                    selected_books.add(missing_list[index]["title"])
            else:
                selected_books.add(item)

        if selected_books:
            print(f"⬇️ Downloading selected books: {', '.join(selected_books)}")
            download_selected_audiobooks(selected_books, missing_list)
        else:
            print("⚠️ No valid selection made. Exiting...")

# Run interactive CLI
if __name__ == "__main__":
    main()
    interactive_missing_audiobooks_cli()
    print("\n🎧 Audible library sync complete!")