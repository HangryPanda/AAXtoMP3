import audible
import json
import os

auth_file = "/host_audible/audibleAuth"

print(f"--- Debugging Auth from {auth_file} ---")

if not os.path.exists(auth_file):
    print(f"ERROR: File {auth_file} does not exist!")
    exit(1)

try:

    print("Attempting to load with locale='us'...")

    auth = audible.Authenticator.from_file(auth_file, locale="us")

    print("Auth object loaded successfully with locale='us'.")

    

    print("\n--- Fetching Library ---")

    with audible.Client(auth=auth) as client:

        # Try a simple fetch first

        try:

            library = client.get("1.0/library", params={"num_results": 5})

            items = library.get("items", [])

            print(f"Found {len(items)} items in library.")

            for item in items:

                print(f" - {item.get('title')} (ASIN: {item.get('asin')})")

        except Exception as e:

            print(f"Error fetching library: {e}")



except Exception as e:

    print(f"Error loading auth with locale: {e}")
