"""
Generate a new Google Drive refresh token for the NSIA dashboard.
Run this locally, then paste the new refresh_token into Streamlit Cloud secrets.

Usage: python scripts/refresh_google_token.py
Requires: .streamlit/secrets.toml with google_drive client_id and client_secret
"""
import os
import sys

try:
    import toml
except ImportError:
    print("Install toml: pip install toml")
    sys.exit(1)

SECRETS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".streamlit", "secrets.toml")

if not os.path.exists(SECRETS_PATH):
    print(f"Secrets file not found: {SECRETS_PATH}")
    print("This script must be run locally where .streamlit/secrets.toml exists.")
    sys.exit(1)

secrets = toml.load(SECRETS_PATH)
gdrive = secrets.get("google_drive", {})

if not gdrive.get("client_id") or not gdrive.get("client_secret"):
    print("Missing client_id or client_secret in [google_drive] section of secrets.toml")
    sys.exit(1)

from google_auth_oauthlib.flow import InstalledAppFlow

CLIENT_CONFIG = {
    "installed": {
        "client_id": gdrive["client_id"],
        "client_secret": gdrive["client_secret"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

flow = InstalledAppFlow.from_client_config(CLIENT_CONFIG, SCOPES)
creds = flow.run_local_server(port=8090, prompt="consent", access_type="offline")

print("\n" + "=" * 60)
print("NEW REFRESH TOKEN (paste into Streamlit Cloud secrets):")
print("=" * 60)
print(creds.refresh_token)
print("=" * 60)
print("\nUpdate your secrets.toml and Streamlit Cloud secrets with this value.")
