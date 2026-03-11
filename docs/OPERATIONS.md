# Server Operations Manual

This document explains how to operate the AI-Editor server locally and what credentials each feature requires.

## 1. What the Server Needs

### Required

- `.env`
  - must contain `SHOTSTACK_KEY`

### Optional, depending on features

- `drive-oauth-client-secret.json`
  - required if users will connect their own Google Drive accounts through the UI

- `drive-token.json`
  - created automatically after Google Drive OAuth succeeds

- `service-account.json`
  - required only if you run Drive access in service-account mode

- `youtube-client-secret.json`
  - required only if you want YouTube upload from the UI

- `youtube-token.json`
  - created automatically after the first successful YouTube login

## 2. Environment File

Create `.env` from `.env.example`.

Minimum local setup:

```env
SHOTSTACK_KEY="your-shotstack-api-key"
GROQ="your-groq-api-key"
DRIVE_AUTH_MODE="oauth_user"
DRIVE_OAUTH_REDIRECT_URI="http://localhost:10000/google-drive/oauth/callback"
YTDLP_SECTION_MODE="fast"
```

### When to change Drive mode

- `DRIVE_AUTH_MODE=oauth_user`
  - preferred for local UI usage
  - users connect their own Google Drive account

- `DRIVE_AUTH_MODE=service_account`
  - use only if the backend should access a shared Drive or shared folder directly
  - requires `service-account.json` or `GOOGLE_APPLICATION_CREDENTIALS`

## 3. Where to Put Credential Files

Place these in the project root unless you override them with environment variables:

- `drive-oauth-client-secret.json`
- `drive-token.json`
- `service-account.json`
- `youtube-client-secret.json`
- `youtube-token.json`

Override variables if you want custom locations:

```env
DRIVE_CLIENT_SECRET_FILE="C:\\path\\to\\drive-oauth-client-secret.json"
DRIVE_TOKEN_FILE="C:\\path\\to\\drive-token.json"
GOOGLE_APPLICATION_CREDENTIALS="C:\\path\\to\\service-account.json"
YOUTUBE_CLIENT_SECRET_FILE="C:\\path\\to\\youtube-client-secret.json"
YOUTUBE_TOKEN_FILE="C:\\path\\to\\youtube-token.json"
```

## 4. Start the Server

### Backend

Run from the project root:

```bash
python -m uvicorn app:app --host 0.0.0.0 --port 10000 --reload
```

Backend endpoints:

- API root: `http://localhost:10000`
- Swagger docs: `http://localhost:10000/docs`
- Drive OAuth callback: `http://localhost:10000/google-drive/oauth/callback`

### Frontend

Run from `frontend/`:

```bash
npm install
npm run dev
```

Default frontend URL:

- `http://localhost:5173`

If needed, set:

```env
VITE_API_BASE_URL=http://localhost:10000
```

## 5. Normal Local Workflow

1. Start backend on port `10000`
2. Start frontend on port `5173`
3. Open the UI
4. Enter the reference video URL
5. Add source videos or a Google Drive folder
6. Use the chat panel to refine the brief
7. Render the edit
8. Review the preview
9. Optionally upload the approved video to YouTube

## 6. Google Drive Operation

### UI OAuth mode

Use this when the user should connect their own Drive account.

Requirements:

- `DRIVE_AUTH_MODE=oauth_user`
- `drive-oauth-client-secret.json` present

Flow:

1. User clicks `Connect Google Drive`
2. Browser opens Google login
3. After success, `drive-token.json` is written locally
4. The backend uses that token for Drive operations

### Service account mode

Use this only when the backend should use one fixed Google service account.

Requirements:

- `DRIVE_AUTH_MODE=service_account`
- `service-account.json` present, or `GOOGLE_APPLICATION_CREDENTIALS` set

Notes:

- the Drive folder must be shared with the service account email
- service-account uploads to normal personal My Drive are limited; OAuth user mode is usually better

## 7. YouTube Upload Operation

Requirements:

- `youtube-client-secret.json` present

Flow:

1. User renders and approves a video
2. User clicks `Upload to YouTube`
3. If `youtube-token.json` does not exist, Google login starts
4. After approval, `youtube-token.json` is written locally
5. Future uploads reuse that saved token

Important:

- changing `youtube-client-secret.json` does not change the upload account by itself
- the active upload account is determined by `youtube-token.json`
- to switch accounts, delete `youtube-token.json` and log in again

## 8. Stop the Server

Stop backend and frontend with `Ctrl+C` in their terminal windows.

## 9. Runtime Files

Per-job files are written to:

```text
tmp/jobs/<job_id>/
```

Common subfolders:

- `debug/`
- `media/`
- `plans/`
- `outputs/`

## 10. Safe Git Practice

Do not commit:

- `.env`
- `drive-oauth-client-secret.json`
- `drive-token.json`
- `service-account.json`
- `youtube-client-secret.json`
- `youtube-token.json`

These are already ignored by `.gitignore`, but do not force-add them.
