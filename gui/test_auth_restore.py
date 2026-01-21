import audible
import json
import sys

auth_file = "/data/auth.json"

try:
    print(f"Loading auth from {auth_file}...")
    auth = audible.Authenticator.from_file(auth_file)
    
    print(f"Marketplace: {getattr(auth, 'market_place', 'Unknown')}")
    if hasattr(auth, 'locale'):
        print(f"Locale Code: {auth.locale.code}")
        print(f"Locale Domain: {auth.locale.domain}")
    else:
        print("Auth object has no 'locale' attribute.")

except Exception as e:
    print(f"Error: {e}")
