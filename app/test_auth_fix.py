import audible
import json
import sys
try:
    import tomllib
except ImportError:
    import toml as tomllib
from pathlib import Path

AUTH_FILE = Path("/data/auth.json")
HOST_AUTH_FILE = Path("/host_audible/audibleAuth")

def get_locale_from_config():
    """Try to determine locale from host config."""
    host_audible_config = Path("/host_audible")
    audible_cli_config = Path("/root/.audible")
    
    for config_path in [host_audible_config, audible_cli_config]:
        if config_path.exists():
            config_toml = config_path / "config.toml"
            if config_toml.exists():
                try:
                    with open(config_toml, "rb") as f:
                        data = tomllib.load(f)
                        primary = data.get("APP", {}).get("primary_profile")
                        if primary:
                            return data.get("profile", {}).get(primary, {}).get("country_code", "us")
                except Exception:
                    pass
    return "us"

locale = get_locale_from_config()
print(f"Detected locale: {locale}")

for fpath in [AUTH_FILE, HOST_AUTH_FILE]:
    if not fpath.exists():
        print(f"Skipping {fpath} (not found)")
        continue
        
    try:
        print(f"\n--- Testing {fpath} ---")
        auth = audible.Authenticator.from_file(fpath, locale=locale)
        with audible.Client(auth=auth) as client:
            library = client.get("1.0/library", params={"num_results": 5})
            items = library.get("items", [])
            print(f"Found {len(items)} items.")
            for item in items:
                print(f" - {item.get('title')}")

    except Exception as e:
        print(f"Error: {e}")
