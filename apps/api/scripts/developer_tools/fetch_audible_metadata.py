
import asyncio
import json
import os
import sys

# Add apps/api to path (3 levels up from scripts/developer_tools)
current_dir = os.path.dirname(os.path.abspath(__file__))
api_root = os.path.abspath(os.path.join(current_dir, "../../.."))
sys.path.append(api_root)

from services.audible_client import AudibleClient

async def main():
    client = AudibleClient()
    print("Checking authentication...")
    if not await client.is_authenticated():
        print("Error: Not authenticated. Check your auth file.")
        return

    print("Fetching one library item for sanity check...")
    try:
        # Fetching with default response groups
        items = await client.get_library(limit=1)
        if items:
            print("\nMETADATA_START")
            print(json.dumps(items[0], indent=2))
            print("METADATA_END")
        else:
            print("No items found in library.")
    except Exception as e:
        print(f"Error fetching library: {e}")

if __name__ == "__main__":
    asyncio.run(main())

