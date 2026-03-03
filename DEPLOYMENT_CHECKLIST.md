# Deployment Checklist & Production Guide

Complete checklist for deploying AI-Editor to production.

---

## Pre-Deployment Phase

### ✅ Code Review & Testing

- [ ] Code review completed (peer or self)
- [ ] All endpoints tested locally
- [ ] All UI components tested (desktop + mobile)
- [ ] Video rendering tested (multiple formats)
- [ ] Error handling tested (all error paths)
- [ ] Performance tested under load
- [ ] Security review completed

**Testing:**
```bash
# Run full test suite
cd AI-Editor

# Backend tests
pytest tests/  # If you have tests

# Frontend tests
cd frontend
npm run test

# Manual testing
python -m uvicorn app:app --reload &
npm run dev

# Test scenarios from FRONTEND_TESTING_GUIDE.md
```

---

### ✅ Environment Configuration

- [ ] Create production `.env` file
- [ ] Set all API keys (Shotstack, Deepseek, Groq)
- [ ] Use production API endpoints (not stage)
- [ ] Set appropriate log levels (`ENV=production`)
- [ ] Configure CORS for production domain
- [ ] Set proper timeouts based on load testing

**Production .env:**
```env
# Production API Keys
SHOTSTACK_API_KEY=your_production_key
SHOTSTACK_HOST=https://api.shotstack.io/production
DEEPSEEK_API_KEY=your_production_key
GROQ_API_KEY=your_production_key

# Environment
ENV=production
LOG_LEVEL=info

# Timeouts
RENDER_TIMEOUT=600
DOWNLOAD_TIMEOUT=300

# Optional: Analytics
SENTRY_DSN=https://...  # Error tracking
```

---

### ✅ System Dependencies

- [ ] FFmpeg installed and in PATH
- [ ] Python 3.8+ installed
- [ ] Node.js 16+ installed
- [ ] Package managers accessible (pip, npm)
- [ ] Disk space available (50GB+ recommended)
- [ ] Memory available (2GB+ recommended)

**Verify:**
```bash
ffmpeg -version      # Should show version
python --version     # Should be 3.8+
node --version       # Should be 16+
which ffmpeg         # Should show path
which python         # Should show path
which node           # Should show path
```

---

### ✅ Infrastructure Setup

- [ ] Server allocated (cloud or on-premise)
- [ ] Database access configured (if needed)
- [ ] File storage configured (S3, GCS, etc.)
- [ ] CDN configured (optional, for video delivery)
- [ ] Monitoring set up (Datadog, New Relic, etc.)
- [ ] Logging aggregation set up (ELK, Splunk, etc.)
- [ ] Backup strategy defined

---

### ✅ Documentation Review

- [ ] [QUICK_START.md](QUICK_START.md) reviewed
- [ ] [README_REFACTOR.md](README_REFACTOR.md) reviewed
- [ ] [API_EXAMPLES.md](API_EXAMPLES.md) reviewed
- [ ] [FRONTEND_TESTING_GUIDE.md](FRONTEND_TESTING_GUIDE.md) reviewed
- [ ] [TROUBLESHOOTING.md](TROUBLESHOOTING.md) reviewed
- [ ] [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) (if upgrading)

---

## Deployment Phase

### Step 1: Server Setup (30 minutes)

```bash
# SSH into production server
ssh user@production.server

# Create app directory
mkdir -p /opt/ai-editor
cd /opt/ai-editor

# Clone or upload code
git clone https://github.com/your-org/ai-editor.git .
# Or: scp -r ./AI-Editor user@server:/opt/ai-editor/

# Create directories
mkdir -p ./tmp/videos
mkdir -p ./logs
chmod 755 ./tmp/videos
chmod 755 ./logs
```

---

### Step 2: Python Environment (10 minutes)

```bash
# Navigate to project
cd /opt/ai-editor

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Verify Python
python --version

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Verify installation
python -c "import fastapi, yt_dlp, langchain; print('✓ Dependencies OK')"
```

---

### Step 3: Environment Configuration (5 minutes)

```bash
# Create production .env
cat > .env << 'EOF'
SHOTSTACK_API_KEY=your_production_key_here
SHOTSTACK_HOST=https://api.shotstack.io/production
DEEPSEEK_API_KEY=your_deepseek_key_here
GROQ_API_KEY=your_groq_key_here
ENV=production
LOG_LEVEL=info
EOF

# Secure .env
chmod 600 .env

# Verify API connections
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print('Keys loaded:', len(os.environ.get('SHOTSTACK_API_KEY', '')))"
```

---

### Step 4: Frontend Build (10 minutes)

```bash
# Navigate to frontend
cd /opt/ai-editor/frontend

# Install Node dependencies
npm install --production

# Build for production
npm run build

# Verify build
ls -la dist/
# Should have: index.html, assets/, etc.

# Check bundle size
du -sh dist/
# Should be < 1MB (minified)
```

---

### Step 5: Backend Start (5 minutes)

**Option A: development (for testing)**
```bash
python -m uvicorn app:app --reload --port 8000 --host 0.0.0.0
# Not recommended for production (reloads waste resources)
```

**Option B: Production with Gunicorn (recommended)**

```bash
# Install gunicorn
pip install gunicorn

# Start with 4 workers
gunicorn app:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 300 \
  --access-logfile ./logs/access.log \
  --error-logfile ./logs/error.log \
  --log-level info
```

**Option C: Using Systemd Service (recommended long-term)**

```bash
# Create service file
sudo tee /etc/systemd/system/ai-editor.service > /dev/null <<EOF
[Unit]
Description=AI-Editor Video Processing Service
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/opt/ai-editor

Environment="PATH=/opt/ai-editor/venv/bin"
ExecStart=/opt/ai-editor/venv/bin/gunicorn app:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 300 \
  --access-logfile ./logs/access.log \
  --error-logfile ./logs/error.log

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl enable ai-editor
sudo systemctl start ai-editor
sudo systemctl status ai-editor

# View logs
sudo journalctl -u ai-editor -f
```

---

### Step 6: Frontend Serving (Nginx recommended)

```bash
# Install Nginx
sudo apt-get install nginx  # Ubuntu/Debian
# or: brew install nginx (macOS)

# Create Nginx config
sudo tee /etc/nginx/sites-enabled/ai-editor > /dev/null <<'EOF'
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # Frontend (React)
    location / {
        root /opt/ai-editor/frontend/dist;
        try_files $uri /index.html;
        
        # Cache busting
        location ~* \.(js|css)$ {
            expires 30d;
            add_header Cache-Control "public, immutable";
        }
    }

    # Backend API
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Increase timeouts for video processing
        proxy_read_timeout 600s;
        proxy_connect_timeout 60s;
    }

    # Swagger docs (optional)
    location /api/docs {
        proxy_pass http://127.0.0.1:8000/docs;
    }
}
EOF

# Enable and test Nginx
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx
```

---

### Step 7: SSL Certificate (5 minutes)

```bash
# Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# Get certificate for domain
sudo certbot certonly --nginx -d yourdomain.com -d www.yourdomain.com

# Auto-renewal (should be automatic)
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer

# Test renewal
sudo certbot renew --dry-run
```

---

### Step 8: Verification (15 minutes)

**Checklist:**
```bash
# ✓ Backend responding
curl http://localhost:8000/docs
# Should show Swagger UI

# ✓ API health
curl http://localhost:8000/health 2>/dev/null || echo "No health endpoint"

# ✓ Frontend accessible
curl https://yourdomain.com | head -20
# Should show HTML

# ✓ Video processing working
curl -X POST https://yourdomain.com/api/process-video-url \
  -H "Content-Type: application/json" \
  -d '{"primary_url":"...","sources":[...],"prompt":"test","music_mode":"original"}'

# ✓ Logs available
tail -f ./logs/error.log
tail -f ./logs/access.log

# ✓ Disk space
df -h
# Should have > 10GB available

# ✓ Memory usage
free -h  # Linux
# or: memory_pressure (macOS)
```

---

### Step 9: Monitoring Setup (Optional but Recommended)

```bash
# Install monitoring tools
sudo apt-get install htop iotop  # System monitoring
pip install psutil prometheus-client  # For metrics

# Setup log rotation
sudo tee /etc/logrotate.d/ai-editor > /dev/null <<EOF
/opt/ai-editor/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
    sharedscripts
    postrotate
        systemctl reload ai-editor > /dev/null 2>&1 || true
    endscript
}
EOF

# Test log rotation
sudo logrotate -f /etc/logrotate.d/ai-editor
```

---

## Post-Deployment Phase

### ✅ Smoke Testing (30 minutes)

1. **Basic functionality**
   ```bash
   # Test with simple YouTube video
   curl -X POST https://yourdomain.com/api/process-video-url \
     -H "Content-Type: application/json" \
     -d '{
       "primary_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
       "sources": [{"label": 1, "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}],
       "prompt": "test",
       "music_mode": "original"
     }'
   ```

2. **Multi-clip workflow**
   - Add multiple sources
   - Test segment clipping
   - Verify output video

3. **Music modes**
   - Test with "original" audio
   - Test with "custom" music URL
   - Verify audio in final video

4. **Error handling**
   - Try invalid URL
   - Try invalid segments
   - Check error messages are helpful

---

### ✅ Performance Monitoring

**Watch for:**
```bash
# CPU usage (should be < 80%)
top -bn1 | head -5

# Memory usage (should be < 75%)
free -h

# Disk usage (should be < 80%)
df -h /opt/ai-editor

# I/O throughput
iostat -x 1

# Network throughput
iftop -n
```

---

### ✅ Security Hardening

- [ ] Firewall rules configured
- [ ] SSH key-based auth only (no passwords)
- [ ] API rate limiting enabled
- [ ] DDoS protection enabled (CloudFlare, AWS WAF, etc.)
- [ ] Regular security updates scheduled
- [ ] Secrets rotated quarterly
- [ ] Backup strategy tested

**Firewall rules (UFW example):**
```bash
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https
sudo ufw enable
```

---

### ✅ Backup & Recovery

```bash
# Create backup script
cat > /opt/ai-editor/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/backups/ai-editor"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup code & config
tar -czf $BACKUP_DIR/ai-editor_$DATE.tar.gz \
  --exclude venv \
  --exclude .npm \
  --exclude __pycache__ \
  --exclude .git \
  /opt/ai-editor/

# Cleanup old backups (keep 30 days)
find $BACKUP_DIR -mtime +30 -delete

echo "Backup completed: ai-editor_$DATE.tar.gz"
EOF

chmod +x /opt/ai-editor/backup.sh

# Schedule daily backups
echo "0 2 * * * /opt/ai-editor/backup.sh" | crontab -
```

---

### ✅ Documentation Update

- [ ] Update runbook with production URLs
- [ ] Document API keys location
- [ ] Document backup location
- [ ] Document emergency procedures
- [ ] Share access info with team
- [ ] Update monitoring dashboards

---

## Maintenance Schedule

### Daily
```bash
# Check service status
systemctl status ai-editor
# Should be: active (running)

# Check logs for errors
grep ERROR ./logs/error.log

# Monitor disk space
df -h
```

### Weekly
```bash
# Check system updates
sudo apt-get update
# and security patches available
sudo apt list --upgradable

# Verify backups completed
ls -lh /backups/ai-editor/
# Should have recent backup file
```

### Monthly
- [ ] Review error logs for patterns
- [ ] Test backup restoration
- [ ] Update documentation
- [ ] Review access logs for suspicious activity
- [ ] Rotate API keys
- [ ] Update dependencies

```bash
# Check Python package updates
pip list --outdated

# Update if safe
pip install --upgrade -r requirements.txt
```

### Quarterly
- [ ] Security audit
- [ ] Performance review
- [ ] Disaster recovery drill
- [ ] Cost optimization review
- [ ] Capacity planning review

---

## Troubleshooting

### Issue: Service won't start

```bash
# Check logs
systemctl status ai-editor
journalctl -u ai-editor -n 50

# Common fixes:
# 1. Port in use: sudo lsof -i :8000
# 2. Permission denied: sudo chown -R www-data /opt/ai-editor
# 3. Missing env: Verify .env file exists
# 4. Missing deps: pip install -r requirements.txt
```

### Issue: High CPU usage

```bash
# Find process using CPU
top -b -n1 | grep -E 'PID|ai-editor'

# Solutions:
# 1. Reduce gunicorn workers: --workers 2
# 2. Check for stuck processes: ps aux | grep python
# 3. Review error logs for infinite loops
```

### Issue: Disk running out

```bash
# Find what's using space
du -sh /opt/ai-editor/*

# Most likely: ./tmp/videos/
# Safe to clean: rm -rf ./tmp/videos/*

# Or setup auto-cleanup:
# */30 * * * * rm -rf /opt/ai-editor/tmp/videos/*
```

---

## Rollback Procedure

If something goes wrong:

```bash
# 1. Stop service
sudo systemctl stop ai-editor

# 2. Restore from backup
cd /
sudo tar -xzf /backups/ai-editor/ai-editor_TIMESTAMP.tar.gz

# 3. Restart service
sudo systemctl start ai-editor

# 4. Verify
curl https://yourdomain.com/api/health
```

---

## Scaling

### Handling More Load

```bash
# Option 1: More gunicorn workers
--workers 8  # If 4 cores available

# Option 2: Load balancer
# Use Nginx upstream (multiple backends)
upstream backend {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
}

# Option 3: Separate machines
# Run backend on machine 1
# Run frontend/Nginx on machine 2
# Use external DB/cache
```

---

## Success Criteria

✅ Deployment successful when:

- [ ] Frontend loads without errors
- [ ] API responds to requests
- [ ] Video processing works (start to finish)
- [ ] Error handling works (graceful failures)
- [ ] Temp files cleaned up automatically
- [ ] Logs are being recorded
- [ ] Performance acceptable (< 5 min for typical job)
- [ ] No error emails/alerts
- [ ] All endpoints documented in Swagger
- [ ] Users can access from production URL

---

**Final Note:** This is a complex application. Test thoroughly before going live. Have a rollback plan ready.

**Support Contacts:**
- Error tracking: Check logs in `./logs/error.log`
- Performance issues: See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Feature requests: Update [README_REFACTOR.md](README_REFACTOR.md)

**Last Updated:** March 2026
**Estimated Deployment Time:** 2-3 hours (first time), 30 min (subsequent)
