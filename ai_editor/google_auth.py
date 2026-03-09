import json
import os
from pathlib import Path
from typing import List, Optional


DEFAULT_CREDENTIAL_FILENAMES = [
    "service-account.json",
    "service_account.json",
    "credentials.json",
    "google-service-account.json",
]

DEFAULT_DRIVE_OAUTH_CLIENT_FILENAMES = [
    "drive-oauth-client-secret.json",
    "drive-client-secret.json",
    "client_secret.json",
]


class GoogleCredentialError(Exception):
    """Raised when Google credential resolution/validation fails."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_google_credentials_path() -> Path:
    """
    Resolve Google credentials path using env var, then fallback file search in repo root.
    Also sets GOOGLE_APPLICATION_CREDENTIALS when fallback file is found.
    """
    env_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if env_path:
        resolved = Path(env_path).expanduser().resolve()
        if not resolved.exists():
            raise GoogleCredentialError(
                f"GOOGLE_APPLICATION_CREDENTIALS points to a missing file: {resolved}"
            )
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(resolved)
        return resolved

    root = _repo_root()
    for name in DEFAULT_CREDENTIAL_FILENAMES:
        candidate = root / name
        if candidate.exists():
            resolved = candidate.resolve()
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(resolved)
            return resolved

    expected = ", ".join(DEFAULT_CREDENTIAL_FILENAMES)
    raise GoogleCredentialError(
        "Google credentials not configured. Set GOOGLE_APPLICATION_CREDENTIALS in .env "
        f"or place a service-account key in repo root named one of: {expected}"
    )


def resolve_drive_oauth_client_secret_path() -> Path:
    env_path = os.getenv("DRIVE_CLIENT_SECRET_FILE")
    if env_path:
        resolved = Path(env_path).expanduser().resolve()
        if not resolved.exists():
            raise GoogleCredentialError(f"DRIVE_CLIENT_SECRET_FILE points to a missing file: {resolved}")
        return resolved

    root = _repo_root()
    for name in DEFAULT_DRIVE_OAUTH_CLIENT_FILENAMES:
        candidate = root / name
        if candidate.exists():
            return candidate.resolve()

    expected = ", ".join(DEFAULT_DRIVE_OAUTH_CLIENT_FILENAMES)
    raise GoogleCredentialError(
        "Drive OAuth client secret not found. Set DRIVE_CLIENT_SECRET_FILE or add one of: "
        f"{expected}. Create OAuth Client ID (Desktop app) in Google Cloud Console."
    )


def resolve_drive_token_path() -> Path:
    return Path(os.getenv("DRIVE_TOKEN_FILE", str(_repo_root() / "drive-token.json"))).expanduser().resolve()


def validate_service_account_json(credentials_path: Path) -> dict:
    """Validate service-account JSON structure and return parsed content."""
    try:
        with credentials_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise GoogleCredentialError(
            f"Failed to parse Google credentials JSON at {credentials_path}: {e}"
        ) from e

    if data.get("type") != "service_account":
        raise GoogleCredentialError(
            "Invalid Google credentials JSON type. Expected type='service_account'. "
            "This usually means you provided an OAuth client JSON. "
            "Create a Service Account key in Google Cloud Console: "
            "IAM & Admin -> Service Accounts -> Keys -> Add key -> JSON."
        )

    client_email = data.get("client_email")
    private_key = data.get("private_key")
    private_key_id = data.get("private_key_id")

    if not client_email:
        raise GoogleCredentialError("Invalid service-account JSON: missing client_email.")
    if not private_key:
        raise GoogleCredentialError("Invalid service-account JSON: missing private_key.")
    if "BEGIN PRIVATE KEY" not in private_key:
        raise GoogleCredentialError(
            "Invalid service-account JSON: private_key is malformed (missing BEGIN PRIVATE KEY)."
        )
    if not private_key_id:
        raise GoogleCredentialError("Invalid service-account JSON: missing private_key_id.")

    print(
        "[google-auth] Using credentials path="
        f"{credentials_path} client_email={client_email} private_key_id={private_key_id}"
    )
    return data


def build_drive_service(scopes: Optional[List[str]] = None):
    """Build Google Drive service using OAuth user flow by default."""
    return _build_drive_service_by_mode(scopes=scopes, auth_mode=None)


def _build_drive_service_by_mode(scopes: Optional[List[str]] = None, auth_mode: Optional[str] = None):
    scopes = scopes or ["https://www.googleapis.com/auth/drive.readonly"]
    mode = (auth_mode or os.getenv("DRIVE_AUTH_MODE", "oauth_user")).strip().lower()
    if mode in {"oauth", "oauth_user", "user"}:
        return build_drive_service_oauth(scopes=scopes)
    if mode in {"service_account", "service-account", "sa"}:
        return build_drive_service_service_account(scopes=scopes)
    raise GoogleCredentialError(
        f"Invalid DRIVE_AUTH_MODE='{mode}'. Expected oauth_user or service_account."
    )


def build_drive_service_service_account(scopes: Optional[List[str]] = None):
    scopes = scopes or ["https://www.googleapis.com/auth/drive.readonly"]
    credentials_path = resolve_google_credentials_path()
    validate_service_account_json(credentials_path)

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ModuleNotFoundError as e:
        raise GoogleCredentialError(
            "Google API dependencies are missing. Install with: "
            "pip install google-auth google-api-python-client"
        ) from e

    try:
        creds = service_account.Credentials.from_service_account_file(
            str(credentials_path),
            scopes=scopes,
        )
        return build("drive", "v3", credentials=creds)
    except Exception as e:
        raise GoogleCredentialError(format_google_auth_error(e)) from e


def build_drive_service_oauth(scopes: Optional[List[str]] = None):
    scopes = scopes or ["https://www.googleapis.com/auth/drive.readonly"]
    token_file = resolve_drive_token_path()

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ModuleNotFoundError as e:
        raise GoogleCredentialError(
            "Google OAuth dependencies are missing. Install with: "
            "pip install google-auth-oauthlib google-api-python-client"
        ) from e

    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_file.write_text(creds.to_json(), encoding="utf-8")
        else:
            resolve_drive_oauth_client_secret_path()
            raise GoogleCredentialError(
                "Drive OAuth not connected. Click 'Connect Google Drive' in the UI and finish login."
            )

    print(f"[google-auth] Using Drive OAuth user token at {token_file}")
    return build("drive", "v3", credentials=creds)


def format_google_auth_error(exc: Exception) -> str:
    """Return actionable troubleshooting text for common Google auth failures."""
    base = str(exc)
    common_fixes = (
        "Common causes and fixes: "
        "1) Wrong JSON type: use a Service Account key JSON (not OAuth client JSON). "
        "2) Corrupted private_key formatting/newlines: re-download key JSON from IAM instead of copy/paste. "
        "3) Key revoked/rotated: create a new key and update GOOGLE_APPLICATION_CREDENTIALS. "
        "4) System clock skew: sync system date/time and timezone, then retry."
    )

    if "invalid_grant" in base and "Invalid JWT Signature" in base:
        return f"Google auth failed: invalid_grant (Invalid JWT Signature). {common_fixes}"

    if "permission" in base.lower() or "insufficient" in base.lower():
        return (
            f"Google auth/permission failed: {base}. "
            "Ensure the Drive folder is shared with the service account email."
        )

    return f"Google authentication failed: {base}. {common_fixes}"
