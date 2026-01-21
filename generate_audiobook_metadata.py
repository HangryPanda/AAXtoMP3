import os
import json
import subprocess

# Define paths
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(ROOT_DIR, "audiobook_library.json")
AUTH_FILE = os.path.expanduser("~/.audible/audibleAuth")

# Function to get activation bytes
def get_activation_bytes():
    if os.path.exists(AUTH_FILE):
        with open(AUTH_FILE, "r") as auth_file:
            auth_data = json.load(auth_file)
            return auth_data.get("activation_bytes", "")
    print("⚠️ Activation bytes not found. Please check ~/.audible/audibleAuth.")
    return ""

ACTIVATION_BYTES = get_activation_bytes()

# Check if activation bytes are found
if not ACTIVATION_BYTES:
    print("❌ No activation bytes found. Exiting...")
    exit(1)

# Initialize audiobook library list
audiobook_library = []

# Scan for .aaxc and .aax files
for file in sorted(os.listdir(ROOT_DIR)):
    if file.endswith(".aaxc") or file.endswith(".aax"):
        file_path = os.path.join(ROOT_DIR, file)
        print(f"🔍 Processing: {file}")

        # Extract metadata using audible-cli
        try:
            cmd = [
                "audible", "meta",
                "--input", file_path,
                "--activation-bytes", ACTIVATION_BYTES,
                "--json"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            metadata = json.loads(result.stdout)

            # Extract relevant metadata
            audiobook_data = {
                "title": metadata.get("title", "Unknown Title"),
                "author": metadata.get("author", "Unknown Author"),
                "narrator": metadata.get("narrator", "Unknown Narrator"),
                "duration": metadata.get("duration", "Unknown"),
                "file_path": file_path,
                "cover_image": metadata.get("cover", ""),
                "chapters_file": file_path.replace(".aaxc", ".json").replace(".aax", ".json"),
                "voucher_file": file_path.replace(".aaxc", ".voucher").replace(".aax", ".voucher")
            }

            audiobook_library.append(audiobook_data)

        except subprocess.CalledProcessError as e:
            print(f"❌ Error extracting metadata for {file}: {e}")

# Write to JSON file
with open(OUTPUT_FILE, "w", encoding="utf-8") as json_file:
    json.dump(audiobook_library, json_file, indent=4)

print(f"✅ Audiobook metadata JSON created: {OUTPUT_FILE}")