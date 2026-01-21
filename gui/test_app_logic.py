from app import get_auth, fetch_library
import audible

print("Testing App Logic...")
auth = get_auth()

if auth:
    print("Auth loaded successfully.")
    print(f"Marketplace: {getattr(auth, 'market_place', 'Unknown')}")
    if hasattr(auth, 'locale'):
        print(f"Locale Code: {auth.locale.code}")
    
    with audible.Client(auth=auth) as client:
        print("Fetching library...")
        items = fetch_library(client, force_refresh=True)
        print(f"Found {len(items)} items.")
else:
    print("Auth failed to load.")
