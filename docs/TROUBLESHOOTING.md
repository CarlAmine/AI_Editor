# Troubleshooting Guide

## Quick Diagnostics

```bash
# Backend running?
curl http://localhost:10000/docs

# FFmpeg installed?
ffmpeg -version

# Python deps installed?
python -c "import fastapi, yt_dlp; print('OK')"
```

## Backend Issues

### Backend does not start

Check:

- `.env` exists in the project root
- `SHOTSTACK_KEY` is set
- dependencies are installed

Run:

```bash
python -m uvicorn app:app --host 0.0.0.0 --port 10000 --reload
```

### Port already in use

```bash
netstat -ano | findstr 10000
```

Then stop the conflicting process.

### `ffmpeg` or `ffprobe` not found

Install FFmpeg and ensure it is on `PATH`.

### Video download fails

Check:

- the source URL is public
- the timestamp range is inside the source duration
- `yt-dlp` is installed

### Shotstack render fails

Check:

- `SHOTSTACK_KEY` in `.env`
- asset URLs are publicly fetchable
- the render payload under `tmp/jobs/<job_id>/plans/`

## Google Drive Issues

### `Drive OAuth client secret not found`

Provide one of:

- `drive-oauth-client-secret.json`
- `drive-client-secret.json`
- or set `DRIVE_CLIENT_SECRET_FILE`

### `Drive OAuth not connected`

This means the backend could not find a valid Drive OAuth token.

Fix:

1. Start backend on `http://localhost:10000`
2. In the UI, click `Connect Google Drive`
3. Finish login
4. Confirm `drive-token.json` was created

### Service account cannot access folder

Check:

- `DRIVE_AUTH_MODE=service_account`
- `service-account.json` is valid
- the Drive folder is shared with the service account email

### Service account upload quota or My Drive problems

Use `DRIVE_AUTH_MODE=oauth_user` instead. It is usually the correct local workflow.

## YouTube Issues

### `YouTube OAuth client secret file not found`

Provide:

- `youtube-client-secret.json`
- or set `YOUTUBE_CLIENT_SECRET_FILE`

### Upload goes to the wrong YouTube account

The active account is controlled by `youtube-token.json`, not by the client secret JSON.

Fix:

1. delete `youtube-token.json`
2. upload again
3. log in with the intended Google account

### YouTube Data API not enabled

Enable `YouTube Data API v3` in the Google Cloud project that owns your OAuth client.

### Upload fails after render download

Check:

- the render URL is reachable
- local `/files/...` mapping resolves correctly
- `YOUTUBE_RENDER_DOWNLOAD_READ_TIMEOUT` if the file is large

## Frontend Issues

### Frontend cannot reach backend

Check:

- backend is running on port `10000`
- frontend uses `VITE_API_BASE_URL=http://localhost:10000` if needed

### Bulk source import not parsed correctly

Use:

```text
https://www.youtube.com/watch?v=abc123 - 10-20, 35-45
https://www.youtube.com/watch?v=def456 - 01:10-01:25
```

## Runtime File Cleanup

Job artifacts are written to:

```text
tmp/jobs/<job_id>/
```

If disk usage becomes large, clean old jobs manually.

## More Information

- [SETUP_GUIDE.md](SETUP_GUIDE.md)
- [OPERATIONS.md](OPERATIONS.md)
- [DEPLOYMENT.md](DEPLOYMENT.md)
