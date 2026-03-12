/* ============================================================
   Architecture Page — Cinematic Dark Editorial
   System diagram, request flow, and module responsibilities
   ============================================================ */

import { motion } from "framer-motion";
import { ArrowRight, ArrowDown } from "lucide-react";

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

const modules = [
  { module: "API Entrypoint", file: "app.py", resp: "All HTTP routes, request validation", color: "oklch(0.75 0.18 70)" },
  { module: "Analyzer", file: "ai_editor/analyzer.py", resp: "Scene detection, OCR, frame analysis", color: "oklch(0.55 0.22 255)" },
  { module: "Chatbot", file: "ai_editor/chatbot_interface.py", resp: "LLM-powered brief refinement", color: "oklch(0.75 0.18 70)" },
  { module: "Downloader", file: "ai_editor/downloader.py", resp: "yt-dlp, Google Drive asset fetch", color: "oklch(0.55 0.22 255)" },
  { module: "Editor", file: "ai_editor/editor.py", resp: "Shotstack timeline construction", color: "oklch(0.75 0.18 70)" },
  { module: "Overlay Planner", file: "ai_editor/overlay_planner.py", resp: "Text/graphic element scheduling", color: "oklch(0.55 0.22 255)" },
  { module: "YouTube Uploader", file: "ai_editor/youtube_uploader.py", resp: "OAuth 2.0 publish flow", color: "oklch(0.75 0.18 70)" },
  { module: "Pipeline Runner", file: "pipeline/runner.py", resp: "Stage orchestration (~60 KB)", color: "oklch(0.55 0.22 255)" },
  { module: "State", file: "pipeline/state.py", resp: "Per-job state machine", color: "oklch(0.75 0.18 70)" },
  { module: "Artifacts", file: "pipeline/artifacts.py", resp: "Job artifact path resolution", color: "oklch(0.55 0.22 255)" },
];

const requestFlow = [
  {
    step: "01",
    title: "Brief Submission",
    desc: "The user types a natural language brief in the React chat interface. The Groq LLM refines it into a structured edit plan JSON.",
    from: "React Frontend",
    to: "Groq LLM",
  },
  {
    step: "02",
    title: "Video Analysis",
    desc: "The reference video is processed by the Analyzer: SceneDetect identifies shot boundaries, EasyOCR/PaddleOCR extract text from key frames.",
    from: "FastAPI Backend",
    to: "Analyzer Module",
  },
  {
    step: "03",
    title: "Pipeline Execution",
    desc: "The Pipeline Runner receives the edit plan and executes ordered stages: asset download, timeline assembly, overlay planning, render submission.",
    from: "Pipeline Runner",
    to: "Ordered Stages",
  },
  {
    step: "04",
    title: "Cloud Rendering",
    desc: "The Editor Builder constructs a Shotstack render spec from clip metadata and timing data. Shotstack renders the timeline in the cloud.",
    from: "Editor Builder",
    to: "Shotstack API",
  },
  {
    step: "05",
    title: "Artifact Storage",
    desc: "All outputs (plans, logs, render URLs) are written to tmp/jobs/<job_id>/ for per-job isolation and retrieval.",
    from: "Pipeline Runner",
    to: "tmp/jobs/<id>/",
  },
  {
    step: "06",
    title: "Export",
    desc: "Optionally, the Shorts Converter reframes the output to 9:16 and the YouTube Uploader publishes it via Google OAuth.",
    from: "Shorts Converter",
    to: "YouTube API",
  },
];

// Interactive pipeline diagram
function PipelineDiagram() {
  const nodes = [
    { id: "user", label: "User / Browser", x: 50, y: 10, color: "oklch(0.55 0.22 255)" },
    { id: "react", label: "React Frontend\n(Vite + REST)", x: 50, y: 25, color: "oklch(0.55 0.22 255)" },
    { id: "fastapi", label: "FastAPI Backend\n(app.py)", x: 50, y: 45, color: "oklch(0.75 0.18 70)" },
    { id: "analyzer", label: "Analyzer\n(EasyOCR · PaddleOCR\n· SceneDetect)", x: 20, y: 65, color: "oklch(0.55 0.22 255)" },
    { id: "chatbot", label: "Chatbot Interface\n(Groq LLM)", x: 80, y: 65, color: "oklch(0.55 0.22 255)" },
    { id: "pipeline", label: "Pipeline Runner\n(pipeline/runner.py)", x: 50, y: 80, color: "oklch(0.75 0.18 70)" },
    { id: "shotstack", label: "Shotstack\n(Cloud Render)", x: 20, y: 95, color: "oklch(0.75 0.18 70)" },
    { id: "youtube", label: "YouTube API\n(OAuth Upload)", x: 80, y: 95, color: "oklch(0.75 0.18 70)" },
  ];

  return (
    <div
      className="relative w-full rounded-sm overflow-hidden"
      style={{
        background: "oklch(0.11 0.015 265)",
        border: "1px solid oklch(1 0 0 / 8%)",
        minHeight: "520px",
        padding: "2rem",
      }}
    >
      {/* Grid background */}
      <div
        className="absolute inset-0 opacity-5"
        style={{
          backgroundImage: `linear-gradient(oklch(0.75 0.18 70 / 0.5) 1px, transparent 1px), linear-gradient(90deg, oklch(0.75 0.18 70 / 0.5) 1px, transparent 1px)`,
          backgroundSize: "40px 40px",
        }}
      />

      <div className="relative z-10 flex flex-col items-center gap-6">
        {/* User */}
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.1 }}
          className="px-6 py-3 rounded-sm text-center text-sm font-medium"
          style={{
            background: "oklch(0.55 0.22 255 / 0.12)",
            border: "1px solid oklch(0.55 0.22 255 / 0.4)",
            color: "oklch(0.55 0.22 255)",
            fontFamily: "'DM Mono', monospace",
            fontSize: "0.75rem",
          }}
        >
          User / Browser
        </motion.div>

        <ArrowDown size={16} style={{ color: "oklch(0.40 0.01 80)" }} />

        {/* React Frontend */}
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.2 }}
          className="px-6 py-3 rounded-sm text-center"
          style={{
            background: "oklch(0.55 0.22 255 / 0.08)",
            border: "1px solid oklch(0.55 0.22 255 / 0.3)",
            color: "oklch(0.55 0.22 255)",
            fontFamily: "'DM Mono', monospace",
            fontSize: "0.75rem",
          }}
        >
          React Frontend (Vite) + REST
        </motion.div>

        <div className="flex items-center gap-2">
          <div className="h-px w-20" style={{ background: "oklch(0.40 0.01 80 / 0.4)" }} />
          <span style={{ color: "oklch(0.40 0.01 80)", fontFamily: "'DM Mono', monospace", fontSize: "0.65rem" }}>REST calls</span>
          <div className="h-px w-20" style={{ background: "oklch(0.40 0.01 80 / 0.4)" }} />
        </div>

        {/* FastAPI */}
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.3 }}
          className="px-8 py-4 rounded-sm text-center"
          style={{
            background: "oklch(0.75 0.18 70 / 0.1)",
            border: "2px solid oklch(0.75 0.18 70 / 0.5)",
            color: "oklch(0.75 0.18 70)",
            fontFamily: "'DM Mono', monospace",
            fontSize: "0.75rem",
            boxShadow: "0 0 20px oklch(0.75 0.18 70 / 0.1)",
          }}
        >
          FastAPI Backend (app.py)
        </motion.div>

        {/* Branch row */}
        <div className="flex items-start gap-8 w-full justify-center">
          {/* Left branch */}
          <div className="flex flex-col items-center gap-4">
            <ArrowDown size={14} style={{ color: "oklch(0.40 0.01 80)" }} />
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.4 }}
              className="px-5 py-3 rounded-sm text-center"
              style={{
                background: "oklch(0.55 0.22 255 / 0.08)",
                border: "1px solid oklch(0.55 0.22 255 / 0.3)",
                color: "oklch(0.55 0.22 255)",
                fontFamily: "'DM Mono', monospace",
                fontSize: "0.7rem",
                maxWidth: "160px",
              }}
            >
              Analyzer<br />
              <span style={{ color: "oklch(0.40 0.01 80)" }}>EasyOCR · PaddleOCR<br />· SceneDetect</span>
            </motion.div>
            <div style={{ color: "oklch(0.40 0.01 80)", fontFamily: "'DM Mono', monospace", fontSize: "0.65rem" }}>Edit Plan JSON</div>
          </div>

          {/* Right branch */}
          <div className="flex flex-col items-center gap-4">
            <ArrowDown size={14} style={{ color: "oklch(0.40 0.01 80)" }} />
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.4 }}
              className="px-5 py-3 rounded-sm text-center"
              style={{
                background: "oklch(0.55 0.22 255 / 0.08)",
                border: "1px solid oklch(0.55 0.22 255 / 0.3)",
                color: "oklch(0.55 0.22 255)",
                fontFamily: "'DM Mono', monospace",
                fontSize: "0.7rem",
                maxWidth: "160px",
              }}
            >
              Chatbot Interface<br />
              <span style={{ color: "oklch(0.40 0.01 80)" }}>Groq LLM</span>
            </motion.div>
            <div style={{ color: "oklch(0.40 0.01 80)", fontFamily: "'DM Mono', monospace", fontSize: "0.65rem" }}>Edit Brief JSON</div>
          </div>
        </div>

        <ArrowDown size={16} style={{ color: "oklch(0.40 0.01 80)" }} />

        {/* Pipeline Runner */}
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.5 }}
          className="px-8 py-4 rounded-sm text-center w-full max-w-xs"
          style={{
            background: "oklch(0.75 0.18 70 / 0.1)",
            border: "2px solid oklch(0.75 0.18 70 / 0.5)",
            color: "oklch(0.75 0.18 70)",
            fontFamily: "'DM Mono', monospace",
            fontSize: "0.75rem",
            boxShadow: "0 0 20px oklch(0.75 0.18 70 / 0.1)",
          }}
        >
          Pipeline Runner<br />
          <span style={{ color: "oklch(0.55 0.01 80)" }}>pipeline/runner.py</span>
        </motion.div>

        {/* Final branches */}
        <div className="flex items-start gap-8 w-full justify-center">
          {["Overlay Planner", "Shorts Converter", "Downloader\n(yt-dlp · Drive)", "Editor Builder\n(Shotstack Timeline)"].map((label, i) => (
            <motion.div
              key={label}
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.6 + i * 0.08 }}
              className="flex flex-col items-center gap-2"
            >
              <ArrowDown size={12} style={{ color: "oklch(0.35 0.01 80)" }} />
              <div
                className="px-3 py-2 rounded-sm text-center"
                style={{
                  background: "oklch(0.16 0.015 265)",
                  border: "1px solid oklch(1 0 0 / 8%)",
                  color: "oklch(0.50 0.01 80)",
                  fontFamily: "'DM Mono', monospace",
                  fontSize: "0.65rem",
                  maxWidth: "110px",
                  whiteSpace: "pre-line",
                }}
              >
                {label}
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function Architecture() {
  return (
    <div className="min-h-screen pt-24">
      {/* ── PAGE HEADER ── */}
      <section className="py-20 relative overflow-hidden">
        <div
          className="absolute inset-0"
          style={{
            background: "radial-gradient(ellipse at 50% 30%, oklch(0.75 0.18 70 / 0.05) 0%, transparent 60%)",
          }}
        />
        <div className="container mx-auto px-6 max-w-7xl relative z-10">
          <FadeUp>
            <span className="section-number block mb-4">System Design</span>
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
              Architecture
            </h1>
            <p
              className="text-base leading-relaxed max-w-xl"
              style={{ color: "oklch(0.55 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}
            >
              A full-stack architecture with FastAPI backend, React frontend, and a multi-stage
              pipeline runner coordinating AI analysis, cloud rendering, and OAuth publishing.
            </p>
          </FadeUp>
        </div>
      </section>

      {/* ── PIPELINE DIAGRAM ── */}
      <section className="pb-16">
        <div className="container mx-auto px-6 max-w-5xl">
          <FadeUp>
            <div className="mb-8">
              <span className="section-number block mb-2">System Diagram</span>
              <h2
                className="text-4xl"
                style={{ fontFamily: "'Bebas Neue', sans-serif", color: "oklch(0.93 0.01 80)", letterSpacing: "0.05em" }}
              >
                Request Flow
              </h2>
            </div>
            <PipelineDiagram />
          </FadeUp>
        </div>
      </section>

      {/* ── REQUEST FLOW ── */}
      <section className="py-24" style={{ background: "oklch(0.11 0.015 265)" }}>
        <div className="container mx-auto px-6 max-w-7xl">
          <FadeUp>
            <span className="section-number block mb-3">Step by Step</span>
            <h2
              className="text-5xl md:text-6xl mb-16"
              style={{ fontFamily: "'Bebas Neue', sans-serif", color: "oklch(0.93 0.01 80)", letterSpacing: "0.02em" }}
            >
              Request Flow
            </h2>
          </FadeUp>

          <div className="space-y-6">
            {requestFlow.map((step, i) => (
              <FadeUp key={step.step} delay={i * 0.08}>
                <div
                  className="p-6 md:p-8 rounded-sm"
                  style={{
                    background: "oklch(0.13 0.015 265)",
                    border: "1px solid oklch(1 0 0 / 6%)",
                    borderLeft: `3px solid ${i % 2 === 0 ? "oklch(0.75 0.18 70)" : "oklch(0.55 0.22 255)"}`,
                  }}
                >
                  <div className="flex flex-col md:flex-row md:items-start gap-6">
                    <span
                      className="text-3xl flex-shrink-0"
                      style={{
                        fontFamily: "'DM Mono', monospace",
                        color: i % 2 === 0 ? "oklch(0.75 0.18 70)" : "oklch(0.55 0.22 255)",
                        fontWeight: 300,
                      }}
                    >
                      {step.step}
                    </span>
                    <div className="flex-1">
                      <h3
                        className="text-2xl mb-2"
                        style={{ fontFamily: "'Bebas Neue', sans-serif", color: "oklch(0.93 0.01 80)", letterSpacing: "0.05em" }}
                      >
                        {step.title}
                      </h3>
                      <p
                        className="text-sm leading-relaxed mb-4"
                        style={{ color: "oklch(0.55 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}
                      >
                        {step.desc}
                      </p>
                      <div className="flex items-center gap-3">
                        <span
                          className="px-3 py-1 rounded-sm text-xs"
                          style={{
                            background: "oklch(0.55 0.22 255 / 0.1)",
                            border: "1px solid oklch(0.55 0.22 255 / 0.3)",
                            color: "oklch(0.55 0.22 255)",
                            fontFamily: "'DM Mono', monospace",
                          }}
                        >
                          {step.from}
                        </span>
                        <ArrowRight size={14} style={{ color: "oklch(0.40 0.01 80)" }} />
                        <span
                          className="px-3 py-1 rounded-sm text-xs"
                          style={{
                            background: "oklch(0.75 0.18 70 / 0.1)",
                            border: "1px solid oklch(0.75 0.18 70 / 0.3)",
                            color: "oklch(0.75 0.18 70)",
                            fontFamily: "'DM Mono', monospace",
                          }}
                        >
                          {step.to}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </FadeUp>
            ))}
          </div>
        </div>
      </section>

      {/* ── MODULE TABLE ── */}
      <section className="py-24">
        <div className="container mx-auto px-6 max-w-7xl">
          <FadeUp>
            <span className="section-number block mb-3">Module Breakdown</span>
            <h2
              className="text-5xl md:text-6xl mb-12"
              style={{ fontFamily: "'Bebas Neue', sans-serif", color: "oklch(0.93 0.01 80)", letterSpacing: "0.02em" }}
            >
              Module Responsibilities
            </h2>
          </FadeUp>

          <FadeUp delay={0.1}>
            <div
              className="rounded-sm overflow-hidden"
              style={{ border: "1px solid oklch(1 0 0 / 8%)" }}
            >
              {/* Table header */}
              <div
                className="grid grid-cols-3 px-6 py-3"
                style={{
                  background: "oklch(0.11 0.015 265)",
                  borderBottom: "1px solid oklch(1 0 0 / 8%)",
                }}
              >
                {["Module", "File", "Responsibility"].map((h) => (
                  <span
                    key={h}
                    className="text-xs tracking-widest uppercase"
                    style={{ fontFamily: "'DM Mono', monospace", color: "oklch(0.40 0.01 80)" }}
                  >
                    {h}
                  </span>
                ))}
              </div>

              {/* Table rows */}
              {modules.map((mod, i) => (
                <motion.div
                  key={mod.module}
                  initial={{ opacity: 0, x: -10 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.05 }}
                  className="grid grid-cols-3 px-6 py-4 transition-colors duration-150"
                  style={{
                    borderBottom: i < modules.length - 1 ? "1px solid oklch(1 0 0 / 5%)" : "none",
                    background: i % 2 === 0 ? "oklch(0.13 0.015 265)" : "oklch(0.115 0.015 265)",
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "oklch(0.16 0.015 265)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = i % 2 === 0 ? "oklch(0.13 0.015 265)" : "oklch(0.115 0.015 265)"; }}
                >
                  <span
                    className="text-sm font-medium"
                    style={{ color: mod.color, fontFamily: "'DM Sans', sans-serif" }}
                  >
                    {mod.module}
                  </span>
                  <span
                    className="text-xs"
                    style={{ color: "oklch(0.45 0.01 80)", fontFamily: "'DM Mono', monospace", alignSelf: "center" }}
                  >
                    {mod.file}
                  </span>
                  <span
                    className="text-sm"
                    style={{ color: "oklch(0.58 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}
                  >
                    {mod.resp}
                  </span>
                </motion.div>
              ))}
            </div>
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
