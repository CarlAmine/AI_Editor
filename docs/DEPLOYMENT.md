# Deployment Guide

This guide covers a basic deployment layout for AI-Editor.

## Pre-Deployment Checklist

- All endpoints tested locally
- Production `.env` prepared
- FFmpeg installed on the server
- Python and Node versions verified
- Disk space available for `tmp/jobs/`
- Credential files stored outside Git

## 1. Server Layout

```bash
git clone https://github.com/CarlAmine/AI_Editor.git /opt/ai-editor
cd /opt/ai-editor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
mkdir -p tmp/jobs
```

## 2. Production Environment

Create `/opt/ai-editor/.env`:

```env
SHOTSTACK_KEY="your-production-shotstack-key"
GROQ="your-groq-key"
DRIVE_AUTH_MODE="oauth_user"
DRIVE_OAUTH_REDIRECT_URI="https://your-domain.example/google-drive/oauth/callback"
YTDLP_SECTION_MODE="fast"
```

Optional:

```env
DRIVE_CLIENT_SECRET_FILE="/opt/ai-editor/secrets/drive-oauth-client-secret.json"
DRIVE_TOKEN_FILE="/opt/ai-editor/secrets/drive-token.json"
GOOGLE_APPLICATION_CREDENTIALS="/opt/ai-editor/secrets/service-account.json"
YOUTUBE_CLIENT_SECRET_FILE="/opt/ai-editor/secrets/youtube-client-secret.json"
YOUTUBE_TOKEN_FILE="/opt/ai-editor/secrets/youtube-token.json"
```

## 3. Credential Files

Do not store real credential files in Git.

Recommended production location:

```text
/opt/ai-editor/secrets/
```

Common files:

- `drive-oauth-client-secret.json`
- `drive-token.json`
- `service-account.json`
- `youtube-client-secret.json`
- `youtube-token.json`

Set permissions:

```bash
chmod 600 /opt/ai-editor/.env
chmod 600 /opt/ai-editor/secrets/*
```

## 4. Frontend Build

```bash
cd /opt/ai-editor/frontend
npm install
npm run build
```

Optional frontend environment:

```env
VITE_API_BASE_URL=https://your-domain.example
```

## 5. Start the Backend

### Development-style run

```bash
/opt/ai-editor/venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port 10000
```

### Systemd service

```ini
[Unit]
Description=AI Editor API
After=network.target

[Service]
WorkingDirectory=/opt/ai-editor
EnvironmentFile=/opt/ai-editor/.env
ExecStart=/opt/ai-editor/venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port 10000
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ai-editor
sudo systemctl start ai-editor
```

## 6. Reverse Proxy

Recommended approach: serve the static frontend from Nginx and proxy the backend API routes explicitly.

Example Nginx configuration:

```nginx
server {
    listen 80;
    server_name your-domain.example;

    location / {
        root /opt/ai-editor/frontend/dist;
        try_files $uri /index.html;
    }

    location /process-video-url {
        proxy_pass http://127.0.0.1:10000;
        proxy_read_timeout 600s;
    }

    location /chat {
        proxy_pass http://127.0.0.1:10000;
        proxy_read_timeout 600s;
    }

    location /upload-approved-video-youtube {
        proxy_pass http://127.0.0.1:10000;
        proxy_read_timeout 600s;
    }

    location /google-drive/ {
        proxy_pass http://127.0.0.1:10000;
        proxy_read_timeout 600s;
    }

    location /files/ {
        proxy_pass http://127.0.0.1:10000;
        proxy_read_timeout 600s;
    }

    location /docs {
        proxy_pass http://127.0.0.1:10000;
        proxy_read_timeout 600s;
    }

    location /openapi.json {
        proxy_pass http://127.0.0.1:10000;
        proxy_read_timeout 600s;
    }
}
```

If you serve frontend and backend from different origins, ensure the frontend points to the correct API base URL.

## 7. Post-Deployment Checks

```bash
curl http://127.0.0.1:10000/docs
systemctl status ai-editor
df -h
```

## 8. Operational Notes

- `tmp/jobs/` will grow over time; monitor disk usage
- OAuth token files persist between restarts
- to switch the YouTube upload account, delete the configured `youtube-token.json`
- to reset Drive OAuth, delete the configured `drive-token.json`

For day-to-day operation, see [OPERATIONS.md](OPERATIONS.md).
