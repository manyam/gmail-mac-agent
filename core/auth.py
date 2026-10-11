import os
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Restrict scope strictly to read-only Gmail access
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailAuthManager:
    """Handles OAuth 2.0 flow, token refresh, and persistence for Gmail API."""

    def __init__(self, credentials_path: Path, token_path: Path):
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)

    def get_credentials(self, interactive: bool = True) -> Credentials:
        """
        Retrieves valid Google OAuth2 credentials.
        If token is expired, refreshes it automatically.
        If token does not exist, runs the local server browser flow.
        """
        creds: Optional[Credentials] = None

        # 1. Load existing token if present
        if self.token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
            except Exception as e:
                print(f"[WARN] Failed to load token from {self.token_path}: {e}")
                creds = None

        # 2. Check if credentials are valid or need refresh
        if creds and creds.valid:
            return creds

        if creds and creds.expired and creds.refresh_token:
            print("[INFO] Gmail OAuth token expired. Refreshing automatically...")
            try:
                creds.refresh(Request())
                self._save_token(creds)
                return creds
            except Exception as e:
                print(f"[WARN] Failed to refresh token: {e}. Initiating re-authentication.")
                creds = None

        # 3. Interactive flow required
        if not interactive:
            raise RuntimeError(
                f"No valid Gmail OAuth token found at {self.token_path} and interactive mode is disabled."
            )

        if not self.credentials_path.exists():
            raise FileNotFoundError(
                f"Google OAuth client secrets file not found at: {self.credentials_path}\n"
                "To get this file:\n"
                "1. Visit https://console.cloud.google.com/apis/credentials\n"
                "2. Create an OAuth 2.0 Client ID with Application type: 'Desktop app'\n"
                "3. Download the JSON file and save it to: "
                f"{self.credentials_path}"
            )

        print("[INFO] Starting browser for Gmail OAuth authentication...")
        flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), SCOPES)
        creds = flow.run_local_server(port=0, prompt="consent")
        self._save_token(creds)
        print(f"[SUCCESS] Gmail authorization complete. Token saved to {self.token_path}")
        return creds

    def _save_token(self, creds: Credentials) -> None:
        """Saves token with restricted file permissions (0600)."""
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.token_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        try:
            os.chmod(self.token_path, 0o600)
        except OSError:
            pass
