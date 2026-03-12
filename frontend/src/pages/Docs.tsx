/* ============================================================
   Docs Page — Cinematic Dark Editorial
   Quick start, API examples, setup guide, and testing
   ============================================================ */

import { motion, AnimatePresence } from "framer-motion";
import { useState } from "react";
import { ChevronDown, Copy, Check, ExternalLink } from "lucide-react";

function FadeUp({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.6, delay }}
    >
      {children}
    </motion.div>
  );
}

function CodeBlock({ code, lang = "bash" }: { code: string; lang?: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className="relative rounded-sm overflow-hidden"
      style={{
        background: "oklch(0.07 0.012 265)",
        border: "1px solid oklch(1 0 0 / 8%)",
      }}
    >
      {/* Header bar */}
      <div
        className="flex items-center justify-between px-4 py-2"
        style={{ borderBottom: "1px solid oklch(1 0 0 / 6%)", background: "oklch(0.09 0.015 265)" }}
      >
        <span
          className="text-xs tracking-widest uppercase"
          style={{ fontFamily: "'DM Mono', monospace", color: "oklch(0.40 0.01 80)" }}
        >
          {lang}
        </span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 text-xs transition-colors duration-200"
          style={{
            fontFamily: "'DM Mono', monospace",
            color: copied ? "oklch(0.65 0.15 150)" : "oklch(0.45 0.01 80)",
          }}
        >
          {copied ? <Check size={12} /> : <Copy size={12} />}
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>
      <pre
        className="p-5 overflow-x-auto text-sm leading-relaxed"
        style={{ fontFamily: "'DM Mono', monospace", color: "oklch(0.75 0.01 80)" }}
      >
        <code>{code}</code>
      </pre>
    </div>
  );
}

interface AccordionItem {
  title: string;
  content: React.ReactNode;
}

function Accordion({ items }: { items: AccordionItem[] }) {
  const [open, setOpen] = useState<number | null>(0);

  return (
    <div className="space-y-2">
      {items.map((item, i) => (
        <div
          key={item.title}
          className="rounded-sm overflow-hidden"
          style={{
            border: `1px solid ${open === i ? "oklch(0.75 0.18 70 / 0.3)" : "oklch(1 0 0 / 8%)"}`,
            background: "oklch(0.13 0.015 265)",
          }}
        >
          <button
            className="w-full flex items-center justify-between px-6 py-4 text-left transition-colors duration-200"
            onClick={() => setOpen(open === i ? null : i)}
          >
            <span
              className="text-base font-medium"
              style={{
                fontFamily: "'DM Sans', sans-serif",
                color: open === i ? "oklch(0.75 0.18 70)" : "oklch(0.80 0.01 80)",
              }}
            >
              {item.title}
            </span>
            <motion.div
              animate={{ rotate: open === i ? 180 : 0 }}
              transition={{ duration: 0.2 }}
            >
              <ChevronDown size={16} style={{ color: "oklch(0.45 0.01 80)" }} />
            </motion.div>
          </button>
          <AnimatePresence>
            {open === i && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.25 }}
                style={{ overflow: "hidden" }}
              >
                <div
                  className="px-6 pb-6"
                  style={{ borderTop: "1px solid oklch(1 0 0 / 6%)" }}
                >
                  <div className="pt-4">{item.content}</div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      ))}
    </div>
  );
}

const quickStartItems: AccordionItem[] = [
  {
    title: "1 — Prerequisites",
    content: (
      <div className="space-y-3">
        <p className="text-sm" style={{ color: "oklch(0.58 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}>
          Ensure you have the following installed before proceeding:
        </p>
        <ul className="space-y-2">
          {["Python 3.10+", "Node.js 18+", "A Shotstack API key (Stage key is free for development)", "Optional: Google Cloud service account for Drive ingestion, Groq API key"].map((item) => (
            <li key={item} className="flex items-center gap-2.5 text-sm" style={{ color: "oklch(0.62 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}>
              <div className="w-1 h-1 rounded-full flex-shrink-0" style={{ background: "oklch(0.75 0.18 70)" }} />
              {item}
            </li>
          ))}
        </ul>
      </div>
    ),
  },
  {
    title: "2 — Clone and Install",
    content: (
      <CodeBlock
        lang="bash"
        code={`git clone https://github.com/CarlAmine/AI_Editor.git
cd AI_Editor
python -m venv .venv && source .venv/bin/activate
# Windows: .venv\\Scripts\\activate
pip install -r requirements.txt`}
      />
    ),
  },
  {
    title: "3 — Configure Environment",
    content: (
      <div className="space-y-4">
        <CodeBlock
          lang="bash"
          code={`cp .env.example .env
# Edit .env with your API keys`}
        />
        <p className="text-sm" style={{ color: "oklch(0.55 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}>
          At minimum, set <code style={{ color: "oklch(0.75 0.18 70)", fontFamily: "'DM Mono', monospace" }}>SHOTSTACK_KEY</code> and{" "}
          <code style={{ color: "oklch(0.75 0.18 70)", fontFamily: "'DM Mono', monospace" }}>GROQ</code> in your .env file.
          See the Tech Stack page for all environment variables.
        </p>
      </div>
    ),
  },
  {
    title: "4 — Run the Backend",
    content: (
      <div className="space-y-4">
        <CodeBlock
          lang="bash"
          code={`python app.py
# API available at http://localhost:8000
# Interactive docs at http://localhost:8000/docs`}
        />
        <p className="text-sm" style={{ color: "oklch(0.55 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}>
          The FastAPI backend starts with Uvicorn. Visit{" "}
          <span style={{ color: "oklch(0.55 0.22 255)", fontFamily: "'DM Mono', monospace" }}>http://localhost:8000/docs</span>{" "}
          for the interactive Swagger UI.
        </p>
      </div>
    ),
  },
  {
    title: "5 — Run the Frontend",
    content: (
      <CodeBlock
        lang="bash"
        code={`cd frontend
npm install
npm run dev
# UI available at http://localhost:5173`}
      />
    ),
  },
  {
    title: "Docker (Optional)",
    content: (
      <CodeBlock
        lang="bash"
        code={`docker build -t ai-editor .
docker run -p 8000:8000 --env-file .env ai-editor`}
      />
    ),
  },
];

const apiExamples: AccordionItem[] = [
  {
    title: "Start a New Edit Job",
    content: (
      <CodeBlock
        lang="bash"
        code={`curl -X POST http://localhost:8000/jobs \\
  -H 'Content-Type: application/json' \\
  -d '{"reference_url": "https://...", "brief": "60s highlight reel, energetic style"}'

# Response:
# {"job_id": "abc123", "status": "queued", "stages": [...]}`}
      />
    ),
  },
  {
    title: "Poll Job Status",
    content: (
      <CodeBlock
        lang="bash"
        code={`curl http://localhost:8000/jobs/{job_id}/status

# Response:
# {
#   "job_id": "abc123",
#   "status": "rendering",
#   "stage": "shotstack_render",
#   "progress": 0.65,
#   "updated_at": "2024-01-15T10:30:00Z"
# }`}
      />
    ),
  },
  {
    title: "Get Rendered Artifact",
    content: (
      <CodeBlock
        lang="bash"
        code={`curl http://localhost:8000/jobs/{job_id}/artifact

# Response:
# {
#   "job_id": "abc123",
#   "render_url": "https://shotstack.io/...",
#   "duration": 60.0,
#   "format": "mp4"
# }`}
      />
    ),
  },
  {
    title: "Trigger YouTube Upload",
    content: (
      <CodeBlock
        lang="bash"
        code={`curl -X POST http://localhost:8000/jobs/{job_id}/publish \\
  -H 'Content-Type: application/json' \\
  -d '{
    "title": "My AI-Edited Video",
    "description": "Created with AI Editor",
    "privacy": "unlisted"
  }'`}
      />
    ),
  },
];

const testingItems: AccordionItem[] = [
  {
    title: "Run All Tests",
    content: (
      <CodeBlock
        lang="bash"
        code={`pytest tests/ -v

# Output:
# tests/test_editor_normalization.py::test_clip_boundary PASSED
# tests/test_overlay_policy.py::test_schedule_enforcement PASSED
# tests/test_text_segments.py::test_segment_parsing PASSED`}
      />
    ),
  },
  {
    title: "Run Specific Suite",
    content: (
      <CodeBlock
        lang="bash"
        code={`# Timeline normalization and clip boundary logic
pytest tests/test_editor_normalization.py -v

# Overlay scheduling and policy enforcement
pytest tests/test_overlay_policy.py -v

# Text segment parsing and validation
pytest tests/test_text_segments.py -v`}
      />
    ),
  },
];

export default function Docs() {
  return (
    <div className="min-h-screen pt-24">
      {/* ── PAGE HEADER ── */}
      <section className="py-20 relative overflow-hidden">
        <div
          className="absolute inset-0"
          style={{
            background: "radial-gradient(ellipse at 30% 50%, oklch(0.75 0.18 70 / 0.05) 0%, transparent 60%)",
          }}
        />
        <div className="container mx-auto px-6 max-w-7xl relative z-10">
          <FadeUp>
            <span className="section-number block mb-4">Documentation</span>
            <h1
              className="text-7xl md:text-9xl leading-none mb-6"
              style={{
                fontFamily: "'Bebas Neue', sans-serif",
                background: "linear-gradient(160deg, oklch(0.95 0.01 80) 0%, oklch(0.75 0.18 70) 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
              }}
            >
              Quick Start
            </h1>
            <p
              className="text-base leading-relaxed max-w-xl mb-8"
              style={{ color: "oklch(0.55 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}
            >
              Get the AI Editor pipeline running locally in minutes. All you need is Python 3.10+,
              Node.js 18+, and a Shotstack API key.
            </p>
            <div className="flex flex-wrap gap-3">
              {[
                { label: "Full Setup Guide", href: "https://github.com/CarlAmine/AI_Editor/blob/main/docs/SETUP_GUIDE.md" },
                { label: "API Examples", href: "https://github.com/CarlAmine/AI_Editor/blob/main/docs/API_EXAMPLES.md" },
                { label: "Deployment", href: "https://github.com/CarlAmine/AI_Editor/blob/main/docs/DEPLOYMENT.md" },
                { label: "Troubleshooting", href: "https://github.com/CarlAmine/AI_Editor/blob/main/docs/TROUBLESHOOTING.md" },
              ].map((link) => (
                <a
                  key={link.label}
                  href={link.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 px-4 py-2 rounded-sm text-sm transition-all duration-200"
                  style={{
                    border: "1px solid oklch(1 0 0 / 12%)",
                    color: "oklch(0.60 0.01 80)",
                    fontFamily: "'DM Sans', sans-serif",
                    background: "oklch(1 0 0 / 0.02)",
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.borderColor = "oklch(0.75 0.18 70 / 0.3)"; e.currentTarget.style.color = "oklch(0.75 0.18 70)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.borderColor = "oklch(1 0 0 / 0.12)"; e.currentTarget.style.color = "oklch(0.60 0.01 80)"; }}
                >
                  <ExternalLink size={12} />
                  {link.label}
                </a>
              ))}
            </div>
          </FadeUp>
        </div>
      </section>

      {/* ── QUICK START ── */}
      <section className="pb-16">
        <div className="container mx-auto px-6 max-w-4xl">
          <FadeUp>
            <span className="section-number block mb-3">Setup</span>
            <h2
              className="text-4xl md:text-5xl mb-8"
              style={{ fontFamily: "'Bebas Neue', sans-serif", color: "oklch(0.93 0.01 80)", letterSpacing: "0.02em" }}
            >
              Installation
            </h2>
            <Accordion items={quickStartItems} />
          </FadeUp>
        </div>
      </section>

      {/* ── API EXAMPLES ── */}
      <section className="py-16" style={{ background: "oklch(0.11 0.015 265)" }}>
        <div className="container mx-auto px-6 max-w-4xl">
          <FadeUp>
            <span className="section-number block mb-3">REST API</span>
            <h2
              className="text-4xl md:text-5xl mb-4"
              style={{ fontFamily: "'Bebas Neue', sans-serif", color: "oklch(0.93 0.01 80)", letterSpacing: "0.02em" }}
            >
              API Examples
            </h2>
            <p
              className="text-sm mb-8"
              style={{ color: "oklch(0.50 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}
            >
              The FastAPI backend exposes a REST API. Interactive docs are at{" "}
              <span style={{ color: "oklch(0.55 0.22 255)", fontFamily: "'DM Mono', monospace" }}>http://localhost:8000/docs</span>
            </p>
            <Accordion items={apiExamples} />
          </FadeUp>
        </div>
      </section>

      {/* ── TESTING ── */}
      <section className="py-16">
        <div className="container mx-auto px-6 max-w-4xl">
          <FadeUp>
            <span className="section-number block mb-3">Testing</span>
            <h2
              className="text-4xl md:text-5xl mb-4"
              style={{ fontFamily: "'Bebas Neue', sans-serif", color: "oklch(0.93 0.01 80)", letterSpacing: "0.02em" }}
            >
              Running Tests
            </h2>
            <p
              className="text-sm mb-8"
              style={{ color: "oklch(0.50 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}
            >
              Three pytest suites cover the core pipeline logic. All tests are in the{" "}
              <span style={{ color: "oklch(0.75 0.18 70)", fontFamily: "'DM Mono', monospace" }}>tests/</span> directory.
            </p>
            <Accordion items={testingItems} />
          </FadeUp>
        </div>
      </section>

      {/* ── REPO STRUCTURE ── */}
      <section className="py-16" style={{ background: "oklch(0.11 0.015 265)" }}>
        <div className="container mx-auto px-6 max-w-4xl">
          <FadeUp>
            <span className="section-number block mb-3">Repository</span>
            <h2
              className="text-4xl md:text-5xl mb-8"
              style={{ fontFamily: "'Bebas Neue', sans-serif", color: "oklch(0.93 0.01 80)", letterSpacing: "0.02em" }}
            >
              Repository Structure
            </h2>
            <CodeBlock
              lang="text"
              code={`AI_Editor/
├── app.py                    # FastAPI entrypoint — all HTTP routes
├── Dockerfile                # Container build
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variable reference
│
├── ai_editor/                # Core AI & media logic
│   ├── analyzer.py           # Scene detection, OCR, video analysis
│   ├── chatbot_interface.py  # Groq-powered brief builder
│   ├── downloader.py         # yt-dlp + Google Drive asset fetching
│   ├── editor.py             # Shotstack timeline assembly
│   ├── overlay_planner.py    # Text/graphic overlay scheduling
│   ├── youtube_clipper.py    # Clip extraction and trimming
│   ├── youtube_uploader.py   # YouTube OAuth upload flow
│   └── google_auth.py        # Google credential management
│
├── pipeline/                 # Orchestration layer
│   ├── runner.py             # Stage runner (main orchestrator ~60 KB)
│   ├── state.py              # Per-job state machine
│   ├── artifacts.py          # Artifact path resolution and storage
│   ├── plans/                # Edit plan schemas and planners
│   └── storage/              # Job storage helpers
│
├── frontend/                 # React UI (Vite)
│
├── docs/                     # Documentation
│   ├── API_EXAMPLES.md
│   ├── DEPLOYMENT.md
│   ├── SETUP_GUIDE.md
│   ├── TROUBLESHOOTING.md
│   └── architecture.md
│
└── tests/
    ├── test_editor_normalization.py
    ├── test_overlay_policy.py
    └── test_text_segments.py`}
            />
          </FadeUp>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 text-center" style={{ borderTop: "1px solid oklch(1 0 0 / 6%)" }}>
        <p className="text-xs tracking-widest uppercase" style={{ fontFamily: "'DM Mono', monospace", color: "oklch(0.35 0.01 80)" }}>
          AI Editor · Open Source · MIT License · by{" "}
          <a href="https://github.com/CarlAmine" target="_blank" rel="noopener noreferrer" style={{ color: "oklch(0.75 0.18 70)" }}>
            CarlAmine
          </a>
        </p>
      </footer>
    </div>
  );
}
