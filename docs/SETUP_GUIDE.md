# Setup Guide

This guide gets the project running locally with the current server layout.

## Prerequisites

- Python 3.10+
- Node.js 18+
- FFmpeg installed and available on `PATH`

Verify:

```bash
ffmpeg -version
python --version
node --version
```

## 1. Clone the Repository

```bash
git clone https://github.com/CarlAmine/AI_Editor.git
cd AI_Editor
```

## 2. Install Backend Dependencies

```bash
pip install -r requirements.txt
```

## 3. Create `.env`

```bash
cp .env.example .env
```

Edit `.env` and set at least:

```env
SHOTSTACK_KEY="your-shotstack-api-key"
GROQ="your-groq-api-key"
DRIVE_AUTH_MODE="oauth_user"
DRIVE_OAUTH_REDIRECT_URI="http://localhost:10000/google-drive/oauth/callback"
```

## 4. Add Optional Credential Files

Add only the files you actually need:

### Google Drive OAuth in the UI

Place in project root:

- `drive-oauth-client-secret.json`

Generated automatically later:

- `drive-token.json`

### Google Drive service account mode

Place in project root:

- `service-account.json`

Or set:

```env
GOOGLE_APPLICATION_CREDENTIALS="C:\\path\\to\\service-account.json"
```

### YouTube upload

Place in project root:

- `youtube-client-secret.json`

Generated automatically later:

- `youtube-token.json`

## 5. Start the Backend

```bash
python -m uvicorn app:app --host 0.0.0.0 --port 10000 --reload
```

Backend URLs:

- API: `http://localhost:10000`
- Swagger docs: `http://localhost:10000/docs`

## 6. Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend URL:

- `http://localhost:5173`

If needed, set `frontend/.env`:

```env
VITE_API_BASE_URL=http://localhost:10000
```

## 7. First-Time Verification

### Backend

```bash
curl http://localhost:10000/docs
```

### Frontend

Open `http://localhost:5173`

### Python dependencies

```bash
python -c "import fastapi, yt_dlp; print('OK')"
```

## 8. Next Step

After setup, use [OPERATIONS.md](OPERATIONS.md) for daily usage and credential handling.
