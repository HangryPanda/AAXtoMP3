import asyncio
import os
import sys
import logging

# Add apps/api to python path
sys.path.append(os.path.join(os.getcwd(), "apps", "api"))

# Configure logging
logging.basicConfig(level=logging.INFO)

from services.audible_client import AudibleClient

async def test_fetch():
    client = AudibleClient()
    
    if not await client.is_authenticated():
        print("Not authenticated. Cannot test fetch.")
        return

    print("Authenticated. Fetching library (limit=1)...")
    try:
        items = await client.get_library(limit=1)
        if items:
            item = items[0]
            print(f"Title: {item.get('title')}")
            print(f"Product Images: {item.get('product_images')}")
            print(f"Authors: {item.get('authors')}")
        else:
            print("No items returned.")
    except Exception as e:
        print(f"Error fetching: {e}")

if __name__ == "__main__":
    asyncio.run(test_fetch())
