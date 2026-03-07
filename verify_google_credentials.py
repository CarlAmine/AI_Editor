"""
Verify local Google service-account credentials for Drive access.

Usage:
  python verify_google_credentials.py
"""

from ai_editor.google_auth import build_drive_service, format_google_auth_error, GoogleCredentialError


def main():
    print("Verifying Google service-account credentials...")
    try:
        drive = build_drive_service(scopes=["https://www.googleapis.com/auth/drive.readonly"])
        about = drive.about().get(fields="user(emailAddress,displayName)").execute()
        user = about.get("user", {})
        print("SUCCESS: Google Drive auth is working.")
        print(f"Authenticated principal: {user.get('emailAddress') or 'unknown'}")
        return 0
    except GoogleCredentialError as e:
        print(f"FAIL: {e}")
        return 1
    except Exception as e:
        print(f"FAIL: {format_google_auth_error(e)}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
