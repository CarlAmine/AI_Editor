# Documentation Index

Complete guide to all AI-Editor documentation and resources.

---

## 🚀 Getting Started (Start Here!)

**New to AI-Editor?** Start with these in order:

1. **[QUICK_START.md](QUICK_START.md)** (15 minutes)
   - System requirements
   - 5-minute setup
   - First test
   - Verification checklist

2. **[README_REFACTOR.md](README_REFACTOR.md)** (30 minutes)
   - Architecture overview
   - How the system works
   - What's new in this version
   - Project structure

3. **[API_EXAMPLES.md](API_EXAMPLES.md)** (interactive)
   - cURL examples
   - Python code samples
   - JavaScript/React examples
   - Testing API locally

4. **[FRONTEND_TESTING_GUIDE.md](FRONTEND_TESTING_GUIDE.md)** (hands-on)
   - 12 test scenarios
   - UI regression tests
   - Error handling tests
   - Performance tests

---

## 📚 Documentation by Topic

### Setup & Configuration

| Document | Purpose | Read Time |
|----------|---------|-----------|
| [QUICK_START.md](QUICK_START.md) | Get running in 15 minutes | 15 min |
| [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) | Deploy to production | 60 min |
| [README_REFACTOR.md](README_REFACTOR.md) | Understand architecture | 30 min |

### API & Integration

| Document | Purpose | Read Time |
|----------|---------|-----------|
| [API_EXAMPLES.md](API_EXAMPLES.md) | How to call the API | 20 min |
| [README_REFACTOR.md](README_REFACTOR.md#architecture) | API design patterns | 15 min |

### Testing & Quality Assurance

| Document | Purpose | Read Time |
|----------|---------|-----------|
| [FRONTEND_TESTING_GUIDE.md](FRONTEND_TESTING_GUIDE.md) | Test the UI | 45 min |
| [API_EXAMPLES.md](API_EXAMPLES.md#testing-the-api) | Test the API | 10 min |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md#testing-the-implementation) | Verify installation | 10 min |

### Troubleshooting & Support

| Document | Purpose | Read Time |
|----------|---------|-----------|
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Fix problems | As needed |
| [QUICK_START.md](QUICK_START.md#common-issues--quick-fixes) | Common issues | 5 min |
| [API_EXAMPLES.md](API_EXAMPLES.md#debugging) | Debug the API | 10 min |

### Deployment & Operations

| Document | Purpose | Read Time |
|----------|---------|-----------|
| [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) | Go live | 60 min |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md#deployment-issues) | Fix deployment | As needed |
| [README_REFACTOR.md](README_REFACTOR.md#performance-notes) | Performance tuning | 15 min |

### Migration (If Upgrading)

| Document | Purpose | Read Time |
|----------|---------|-----------|
| [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) | Upgrade from old version | 30 min |
| [README_REFACTOR.md](README_REFACTOR.md#breaking-changes) | What changed | 10 min |

---

## 🎯 Find What You Need

### "I want to..."

#### ...set up AI-Editor locally
→ See: [QUICK_START.md](QUICK_START.md)

#### ...understand how it works
→ See: [README_REFACTOR.md](README_REFACTOR.md)

#### ...use the API
→ See: [API_EXAMPLES.md](API_EXAMPLES.md)

#### ...test the system
→ See: [FRONTEND_TESTING_GUIDE.md](FRONTEND_TESTING_GUIDE.md)

#### ...deploy to production
→ See: [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)

#### ...fix a problem
→ See: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

#### ...migrate from old version
→ See: [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)

#### ...understand the architecture
→ See: [README_REFACTOR.md](README_REFACTOR.md#architecture)

#### ...write code using the API
→ See: [API_EXAMPLES.md](API_EXAMPLES.md)

#### ...deploy and monitor
→ See: [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md#post-deployment-phase)

---

## 📖 Full Document Guide

### QUICK_START.md ⭐ START HERE
**Purpose:** Get AI-Editor running in 15 minutes

**Sections:**
- Prerequisites
- Environment setup
- Backend setup
- Frontend setup
- First test
- Workflow overview
- File structure
- Common issues
- Next steps

**Best for:** New users, quick setup

**Time to read:** 15 minutes

---

### README_REFACTOR.md
**Purpose:** Understand the complete architecture and system design

**Sections:**
- Overview of changes
- Key features
- Architecture explanation
- Complete workflow (9 steps)
- File structure and modules
- Environment variables
- API endpoints
- Examples and use cases
- Performance notes
- Troubleshooting
- Contributing guide

**Best for:** Developers, architects, deep understanding

**Time to read:** 30 minutes

**Key concepts:**
- 9-step pipeline for video processing
- URL-based instead of file upload
- Job-based temp directory cleanup
- Music mode selection (original vs custom)
- Multi-source clip ordering

---

### API_EXAMPLES.md
**Purpose:** Show practical examples of using the API

**Sections:**
- cURL examples (basic to advanced)
- Python examples (from simple to batch processing)
- JavaScript/React examples
- Response formats
- Segment format reference
- Postman testing
- Swagger UI
- Debugging tips

**Best for:** API developers, integration work, testing

**Time to read:** 20 minutes

**Quick examples:**
```bash
# Single video
curl -X POST http://localhost:8000/process-video-url \
  -H "Content-Type: application/json" \
  -d '{"primary_url":"...","sources":[...],"prompt":"...","music_mode":"original"}'

# Python
processor = VideoProcessor()
result = processor.process_videos(...)

# JavaScript
await fetch("http://localhost:8000/process-video-url", {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify(payload)
})
```

---

### FRONTEND_TESTING_GUIDE.md
**Purpose:** Comprehensive testing procedures and QA guide

**Sections:**
- Prerequisites
- 12 detailed test scenarios
- UI regression tests
- Performance tests
- Browser compatibility tests
- Testing checklist
- Common issues & fixes
- Debugging tools

**Best for:** QA engineers, testers, validation

**Time to read:** 45 minutes

**Test coverage:**
- Single video workflow
- Multi-clip with segments
- Source reordering
- Music mode selection
- Segment format validation
- TikTok support
- Cleanup verification
- Long-running renders
- Error handling
- Network failures
- Multi-user scenarios

---

### TROUBLESHOOTING.md
**Purpose:** Diagnose and fix problems

**Sections:**
- General diagnostics
- Backend issues (port, modules, FFmpeg, downloads, rendering)
- Frontend issues (connection, segments, form submission, music mode)
- Network issues
- Deployment issues
- Data issues
- Performance optimization
- Debug logging
- Getting help
- Resource links

**Best for:** Problem solving, debugging, maintenance

**Time to read:** As needed (reference)

**Common issues covered:**
- Port already in use
- Missing dependencies
- FFmpeg not found
- Network timeouts
- Video download failures
- Render failures
- Cleanup not working
- CORS errors
- Slow performance

---

### DEPLOYMENT_CHECKLIST.md
**Purpose:** Deploy AI-Editor to production

**Sections:**
- Pre-deployment phase
  - Code review
  - Environment configuration
  - System dependencies
  - Infrastructure setup
  - Documentation review
- Deployment phase (9 detailed steps)
  - Server setup
  - Python environment
  - Environment config
  - Frontend build
  - Backend start
  - Frontend serving (Nginx)
  - SSL certificate
  - Verification
  - Monitoring setup
- Post-deployment phase
  - Smoke testing
  - Performance monitoring
  - Security hardening
  - Backup & recovery
- Maintenance schedule
- Troubleshooting specific to production
- Rollback procedure
- Scaling guide

**Best for:** DevOps, system administrators, production deployments

**Time to read:** 60 minutes

**Estimated deployment time:** 2-3 hours (first time), 30 min (subsequent)

---

### MIGRATION_GUIDE.md
**Purpose:** Upgrade from old version to new architecture

**Sections:**
- Quick reference comparison
- Breaking changes
- Step-by-step migration
- Code examples (before/after)
- Testing guide
- Rollback plan
- New features to leverage

**Best for:** Existing users upgrading, understanding changes

**Time to read:** 30 minutes

**Key changes:**
- Remove Google Drive code
- Add YouTube/TikTok download support
- Update API endpoints
- Refactor frontend UI
- Implement local cleanup
- Add music mode selection

---

## 🔑 Key Concepts

### Architecture

**The 9-Step Pipeline:**
1. Download primary video for analysis
2. Analyze video content with LLM
3. Generate requirements report
4. Generate overlay plan
5. Download and clip source videos
6. Extract/handle audio (original or custom)
7. Determine output resolution
8. Build final overlay plan
9. Render with Shotstack

**Job Management:**
- Each request gets unique job ID
- Temp file: `./tmp/videos/{job_id}/`
- Automatic cleanup in finally block
- Survives render success or failure

**Data Flow:**
```
User Input → Validation → Download → Analyze → Plan → Clip → Render → Output
                                                                  ↓
                                          Cleanup (always runs)
```

### Key Files

| File | Purpose |
|------|---------|
| `app.py` | FastAPI main application, endpoints |
| `ai_editor/pipeline.py` | Core orchestration logic |
| `ai_editor/downloader.py` | YouTube/TikTok download & clip |
| `ai_editor/analyzer.py` | LLM-based video analysis |
| `ai_editor/editor.py` | Shotstack video rendering |
| `frontend/src/components/VideoPipelinePanel.tsx` | Main UI component |
| `requirements.txt` | Python dependencies |
| `frontend/package.json` | Node dependencies |

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/process-video-url` | Submit video for processing |
| GET | `/docs` | Swagger UI documentation |
| GET | `/health` | Health check (if implemented) |

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `SHOTSTACK_API_KEY` | Authentication for Shotstack |
| `SHOTSTACK_HOST` | API endpoint (stage or production) |
| `DEEPSEEK_API_KEY` | LLM for analysis |
| `GROQ_API_KEY` | LLM for chat |
| `ENV` | Environment (development/production) |

---

## 🧪 Testing Quick Reference

### Unit Test
```bash
cd AI-Editor
python -m pytest tests/
```

### Integration Test
```bash
# Start backend
python -m uvicorn app:app --reload

# Start frontend
cd frontend && npm run dev

# Test with API_EXAMPLES.md samples
```

### Performance Test
See: [FRONTEND_TESTING_GUIDE.md](FRONTEND_TESTING_GUIDE.md#performance-tests)

### Security Test
See: [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md#optional-but-recommended)

---

## 📞 Getting Help

### Documentation
1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) first
2. Search relevant guide for your topic
3. Check backend logs: `./logs/error.log`
4. Check frontend console: DevTools → Console

### When Reporting Issues
Provide:
- Error message (complete text)
- Steps to reproduce
- System info (OS, Python version)
- Relevant logs
- What you've already tried

Example from [TROUBLESHOOTING.md](TROUBLESHOOTING.md#getting-help):
```
Issue: Video download fails
Error: "Connection timeout"
Steps: [describe exactly]
System: macOS 12.6, Python 3.10
Logs: [paste relevant section]
Already tried: [list attempts]
```

---

## 📋 Checklist for Different Roles

### For Developers
- [ ] Read [QUICK_START.md](QUICK_START.md)
- [ ] Read [README_REFACTOR.md](README_REFACTOR.md)
- [ ] Read [API_EXAMPLES.md](API_EXAMPLES.md)
- [ ] Run [FRONTEND_TESTING_GUIDE.md](FRONTEND_TESTING_GUIDE.md) tests
- [ ] Study `ai_editor/pipeline.py` code
- [ ] Study `frontend/src/components/VideoPipelinePanel.tsx`

### For QA/Testers
- [ ] Read [QUICK_START.md](QUICK_START.md)
- [ ] Read [FRONTEND_TESTING_GUIDE.md](FRONTEND_TESTING_GUIDE.md)
- [ ] Read [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- [ ] Complete all 12 test scenarios
- [ ] Test error cases
- [ ] Test performance

### For DevOps/SysAdmins
- [ ] Read [QUICK_START.md](QUICK_START.md)
- [ ] Read [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)
- [ ] Read [TROUBLESHOOTING.md](TROUBLESHOOTING.md#deployment-issues)
- [ ] Plan monitoring setup
- [ ] Plan backup strategy
- [ ] Security review

### For Upgrading Users
- [ ] Read [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)
- [ ] Read [README_REFACTOR.md](README_REFACTOR.md#breaking-changes)
- [ ] Follow step-by-step migration
- [ ] Test before deploying

---

## 🗺️ Documentation Map

```
START HERE
    ↓
[QUICK_START.md] - Get it running (15 min)
    ↓
    ├─→ Want deep understanding?
    │   └─→ [README_REFACTOR.md]
    │
    ├─→ Want to use the API?
    │   └─→ [API_EXAMPLES.md]
    │
    ├─→ Want to test it?
    │   └─→ [FRONTEND_TESTING_GUIDE.md]
    │
    ├─→ Something broken?
    │   └─→ [TROUBLESHOOTING.md]
    │
    ├─→ Ready to deploy?
    │   └─→ [DEPLOYMENT_CHECKLIST.md]
    │
    └─→ Upgrading from old version?
        └─→ [MIGRATION_GUIDE.md]
```

---

## ✅ Verification Checklist

Before using AI-Editor:

- [ ] Read [QUICK_START.md](QUICK_START.md)
- [ ] Follow setup steps (works on your system)
- [ ] Run first test successfully
- [ ] Can access frontend: `http://localhost:5173`
- [ ] Can access API docs: `http://localhost:8000/docs`
- [ ] Understand basic workflow from [README_REFACTOR.md](README_REFACTOR.md)

Before deploying to production:

- [ ] All code reviewed
- [ ] All tests from [FRONTEND_TESTING_GUIDE.md](FRONTEND_TESTING_GUIDE.md) pass
- [ ] Follow [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)
- [ ] Monitoring and logging set up
- [ ] Backup plan in place
- [ ] Can rollback quickly

---

## 📞 Support Matrix

| Question | Answer Location | Time |
|----------|-----------------|------|
| "How do I get it running?" | [QUICK_START.md](QUICK_START.md) | 15 min |
| "How does it work?" | [README_REFACTOR.md](README_REFACTOR.md) | 30 min |
| "How do I call the API?" | [API_EXAMPLES.md](API_EXAMPLES.md) | 20 min |
| "How do I test it?" | [FRONTEND_TESTING_GUIDE.md](FRONTEND_TESTING_GUIDE.md) | 45 min |
| "Something's broken" | [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | varies |
| "How do I deploy?" | [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) | 60 min |
| "What changed?" | [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) | 30 min |

---

## 📊 Documentation Statistics

| Document | Length | Read Time | Topics |
|----------|--------|-----------|--------|
| QUICK_START.md | ~400 lines | 15 min | Setup, test |
| README_REFACTOR.md | ~600 lines | 30 min | Architecture, API |
| API_EXAMPLES.md | ~500 lines | 20 min | Code samples |
| FRONTEND_TESTING_GUIDE.md | ~400 lines | 45 min | Testing |
| TROUBLESHOOTING.md | ~600 lines | varies | Problems |
| DEPLOYMENT_CHECKLIST.md | ~700 lines | 60 min | Production |
| MIGRATION_GUIDE.md | ~400 lines | 30 min | Upgrading |
| **Total** | **~3,600 lines** | **~3.5 hours** | **Complete coverage** |

---

## 🎓 Learning Path

### Path 1: New User (1.5 hours)
1. QUICK_START.md (15 min) - Get running
2. README_REFACTOR.md intro (15 min) - Understand basics
3. API_EXAMPLES.md basic (10 min) - See examples
4. Hands-on testing (30 min) - Try it yourself
5. FRONTEND_TESTING_GUIDE.md section 1 (20 min) - Learn to test

### Path 2: Developer (3 hours)
1. QUICK_START.md (15 min) - Setup
2. README_REFACTOR.md full (30 min) - Architecture
3. API_EXAMPLES.md full (20 min) - All examples
4. FRONTEND_TESTING_GUIDE.md full (45 min) - All tests
5. Code review (60 min) - Study implementation
6. TROUBLESHOOTING.md (15 min) - Problem solving

### Path 3: DevOps (1.5 hours)
1. QUICK_START.md (15 min) - Understand system
2. DEPLOYMENT_CHECKLIST.md (60 min) - Deployment steps
3. TROUBLESHOOTING.md deployment section (15 min) - Fixes
4. Hands-on practice (20 min) - Test deployment

### Path 4: Upgrading User (1 hour)
1. MIGRATION_GUIDE.md (30 min) - What changed
2. README_REFACTOR.md breaking changes (15 min) - Details
3. QUICK_START.md (15 min) - New setup

---

**Version:** 2.0 (Post-Refactor)  
**Last Updated:** March 2026  
**Total Documentation:** 7 guides, ~3,600 lines  
**Coverage:** Complete from setup to deployment  
**Status:** ✅ Production Ready

---

**Start with:** [QUICK_START.md](QUICK_START.md) ⭐
