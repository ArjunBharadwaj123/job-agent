"""
One-time helper: mint a Gmail read-only refresh token.

Run locally (needs a browser):  PYTHONPATH=src python src/gmail_auth.py

Uses GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET from the environment, opens Google's
consent screen, and prints GMAIL_REFRESH_TOKEN. Add that value to .env and to
the GitHub Actions secrets so the daily scan can read your inbox.

Scope is read-only (gmail.readonly) -- the agent can read but never modify mail.
"""

import os

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def main():
    client_id = os.environ.get("GMAIL_CLIENT_ID")
    client_secret = os.environ.get("GMAIL_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise SystemExit(
            "Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET (source .env) first."
        )

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    # Opens a browser; prompt=consent forces a refresh_token to be returned.
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    print("\n" + "=" * 60)
    print("SUCCESS — add this to .env and to GitHub Actions secrets:")
    print("=" * 60)
    print(f"\nGMAIL_REFRESH_TOKEN={creds.refresh_token}\n")


if __name__ == "__main__":
    main()
