# Deployment Guide

---

## Pre-Deployment Checklist

- [ ] All endpoints tested locally
- [ ] Production `.env` configured with live API keys
- [ ] FFmpeg installed on server
- [ ] Disk space available (50 GB+ recommended)

---

## 1. Server Setup

```bash
git clone https://github.com/CarlAmine/AI_Editor.git /opt/ai-editor
cd /opt/ai-editor
mkdir -p tmp/videos logs
```

## 2. Python Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 3. Environment Variables

```bash
cp .env.example .env
chmod 600 .env
# Edit .env with production keys
```

Production `.env`:
```env
SHOTSTACK_KEY=your_production_key
SHOTSTACK_HOST=https://api.shotstack.io/production
DEEPSEEK_KEY=your_deepseek_key
GROQ=your_groq_key
```

## 4. Frontend Build

```bash
cd frontend
npm install
npm run build
# Output in frontend/dist/
```

## 5. Start Backend

**Development:**
```bash
python -m uvicorn app:app --reload --port 8000
```

**Production (Gunicorn):**
```bash
pip install gunicorn
gunicorn app:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 300
```

**Systemd service** (recommended for production):
```ini
# /etc/systemd/system/ai-editor.service
[Unit]
Description=AI Editor
After=network.target

[Service]
WorkingDirectory=/opt/ai-editor
ExecStart=/opt/ai-editor/venv/bin/gunicorn app:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --timeout 300
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable ai-editor
sudo systemctl start ai-editor
```

## 6. Nginx (Optional)

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        root /opt/ai-editor/frontend/dist;
        try_files $uri /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_read_timeout 600s;
    }
}
```

---

## Post-Deployment Verification

```bash
curl https://yourdomain.com/api/docs    # Swagger UI loads
df -h                                   # Disk space OK
systemctl status ai-editor              # Service running
```

---

## Maintenance

- **Daily:** Check `logs/error.log` and disk usage
- **Weekly:** Review system updates
- **Monthly:** Rotate API keys, update dependencies

---

**Last Updated:** March 2026
