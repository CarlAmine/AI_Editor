/* ============================================================
   Tech Stack Page — Cinematic Dark Editorial
   All technologies, layers, and their roles in the pipeline
   ============================================================ */

import { motion } from "framer-motion";

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

const layers = [
  {
    layer: "Backend API",
    tech: "Python 3.10+, FastAPI, Uvicorn",
    desc: "High-performance async REST API with automatic OpenAPI docs at /docs. FastAPI's type system ensures request validation and serialization.",
    tags: ["Python 3.10+", "FastAPI", "Uvicorn", "Pydantic"],
    color: "oklch(0.75 0.18 70)",
    num: "01",
  },
  {
    layer: "AI / Analysis",
    tech: "EasyOCR, PaddleOCR, SceneDetect, OpenCV, Groq API",
    desc: "Computer vision stack for video analysis. SceneDetect identifies shot boundaries, EasyOCR and PaddleOCR extract text from frames, OpenCV handles frame-level processing.",
    tags: ["EasyOCR", "PaddleOCR", "SceneDetect", "OpenCV", "Groq API"],
    color: "oklch(0.55 0.22 255)",
    num: "02",
  },
  {
    layer: "Edit Planning",
    tech: "Custom planner + LLM-assisted brief builder",
    desc: "A hybrid planning system combining custom rule-based logic with Groq LLM for natural language brief refinement. Output is a structured edit plan JSON.",
    tags: ["Custom Planner", "Groq LLM", "Edit Plan JSON", "Brief Builder"],
    color: "oklch(0.75 0.18 70)",
    num: "03",
  },
  {
    layer: "Rendering",
    tech: "Shotstack SDK (cloud video rendering)",
    desc: "Shotstack's cloud rendering API handles timeline assembly and video rendering. The SDK is used to construct render specs programmatically from clip metadata.",
    tags: ["Shotstack SDK", "Cloud Rendering", "Timeline Assembly", "REST API"],
    color: "oklch(0.55 0.22 255)",
    num: "04",
  },
  {
    layer: "Asset Ingestion",
    tech: "yt-dlp, Google Drive API (service account + OAuth)",
    desc: "Flexible asset sourcing from YouTube via yt-dlp and Google Drive via service account or OAuth credentials. Supports folder-based organization.",
    tags: ["yt-dlp", "Google Drive API", "Service Account", "OAuth 2.0"],
    color: "oklch(0.75 0.18 70)",
    num: "05",
  },
  {
    layer: "Export",
    tech: "YouTube Data API v3, Google Auth OAuthlib",
    desc: "Full YouTube publishing integration with OAuth 2.0 authentication, video metadata management, and direct publish from the pipeline.",
    tags: ["YouTube Data API v3", "Google Auth", "OAuthlib", "OAuth 2.0"],
    color: "oklch(0.55 0.22 255)",
    num: "06",
  },
  {
    layer: "Frontend",
    tech: "React + Vite",
    desc: "React SPA with Vite for fast development and optimized builds. Provides job status tracking, chat interface for brief building, and Google Drive/YouTube OAuth flows.",
    tags: ["React 18", "Vite", "TypeScript", "REST Client"],
    color: "oklch(0.75 0.18 70)",
    num: "07",
  },
  {
    layer: "Tests",
    tech: "pytest",
    desc: "Comprehensive pytest test suites covering timeline normalization, overlay policy enforcement, and text segment parsing. Run with pytest tests/ -v.",
    tags: ["pytest", "Unit Tests", "Coverage", "CI-ready"],
    color: "oklch(0.55 0.22 255)",
    num: "08",
  },
  {
    layer: "Containerization",
    tech: "Docker",
    desc: "Docker container for consistent deployment. The Dockerfile builds a production-ready image with all Python dependencies and environment configuration.",
    tags: ["Docker", "Dockerfile", "Container", "Production Deploy"],
    color: "oklch(0.75 0.18 70)",
    num: "09",
  },
];

const envVars = [
  { var: "SHOTSTACK_KEY", required: true, desc: "Shotstack API key (Stage or Production)" },
  { var: "GROQ", required: true, desc: "Groq API key for conversational brief builder" },
  { var: "GOOGLE_APPLICATION_CREDENTIALS", required: false, desc: "Path to service account JSON for Drive access" },
  { var: "VIDEO_FOLDER", required: false, desc: "Google Drive folder ID for source assets" },
  { var: "MUSIC_URL", required: false, desc: "Default background music track URL" },
  { var: "DEEPSEEK_KEY", required: false, desc: "Reserved for future LLM integration" },
];

export default function Stack() {
  return (
    <div className="min-h-screen pt-24">
      {/* ── PAGE HEADER ── */}
      <section className="py-20 relative overflow-hidden">
        <div
          className="absolute inset-0"
          style={{
            background: "radial-gradient(ellipse at 70% 30%, oklch(0.55 0.22 255 / 0.05) 0%, transparent 60%)",
          }}
        />
        <div className="container mx-auto px-6 max-w-7xl relative z-10">
          <FadeUp>
            <span className="section-number block mb-4">Technology</span>
            <h1
              className="text-7xl md:text-9xl leading-none mb-6"
              style={{
                fontFamily: "'Bebas Neue', sans-serif",
                background: "linear-gradient(160deg, oklch(0.95 0.01 80) 0%, oklch(0.55 0.22 255) 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
              }}
            >
              Tech Stack
            </h1>
            <p
              className="text-base leading-relaxed max-w-xl"
              style={{ color: "oklch(0.55 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}
            >
              A carefully chosen set of technologies spanning AI, computer vision, cloud rendering,
              and full-stack web development.
            </p>
          </FadeUp>
        </div>
      </section>

      {/* ── STACK LAYERS ── */}
      <section className="pb-24">
        <div className="container mx-auto px-6 max-w-7xl">
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {layers.map((layer, i) => (
              <FadeUp key={layer.layer} delay={i * 0.07}>
                <div
                  className="p-7 rounded-sm card-lift h-full flex flex-col"
                  style={{
                    background: "oklch(0.13 0.015 265)",
                    border: "1px solid oklch(1 0 0 / 6%)",
                    borderTop: `2px solid ${layer.color}`,
                  }}
                >
                  <div className="flex items-start justify-between mb-4">
                    <span
                      className="text-xs"
                      style={{ fontFamily: "'DM Mono', monospace", color: layer.color, letterSpacing: "0.1em" }}
                    >
                      {layer.num}
                    </span>
                    <div
                      className="px-2 py-0.5 rounded-sm text-xs"
                      style={{
                        background: `${layer.color.replace(")", " / 0.1)")}`,
                        border: `1px solid ${layer.color.replace(")", " / 0.25)")}`,
                        color: layer.color,
                        fontFamily: "'DM Mono', monospace",
                        fontSize: "0.65rem",
                      }}
                    >
                      Layer {layer.num}
                    </div>
                  </div>

                  <h3
                    className="text-2xl mb-2"
                    style={{ fontFamily: "'Bebas Neue', sans-serif", color: "oklch(0.93 0.01 80)", letterSpacing: "0.05em" }}
                  >
                    {layer.layer}
                  </h3>
                  <p
                    className="text-xs mb-4"
                    style={{ color: layer.color, fontFamily: "'DM Mono', monospace", letterSpacing: "0.03em" }}
                  >
                    {layer.tech}
                  </p>
                  <p
                    className="text-sm leading-relaxed mb-5 flex-1"
                    style={{ color: "oklch(0.55 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}
                  >
                    {layer.desc}
                  </p>

                  <div className="flex flex-wrap gap-2 mt-auto">
                    {layer.tags.map((tag) => (
                      <span
                        key={tag}
                        className="px-2 py-0.5 rounded-sm text-xs"
                        style={{
                          background: "oklch(1 0 0 / 0.04)",
                          border: "1px solid oklch(1 0 0 / 0.08)",
                          color: "oklch(0.50 0.01 80)",
                          fontFamily: "'DM Mono', monospace",
                          fontSize: "0.65rem",
                        }}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </FadeUp>
            ))}
          </div>
        </div>
      </section>

      {/* ── ENV VARS ── */}
      <section className="py-24" style={{ background: "oklch(0.11 0.015 265)" }}>
        <div className="container mx-auto px-6 max-w-7xl">
          <FadeUp>
            <span className="section-number block mb-3">Configuration</span>
            <h2
              className="text-5xl md:text-6xl mb-12"
              style={{ fontFamily: "'Bebas Neue', sans-serif", color: "oklch(0.93 0.01 80)", letterSpacing: "0.02em" }}
            >
              Environment Variables
            </h2>
          </FadeUp>

          <FadeUp delay={0.1}>
            <div
              className="rounded-sm overflow-hidden"
              style={{ border: "1px solid oklch(1 0 0 / 8%)" }}
            >
              {/* Header */}
              <div
                className="grid grid-cols-12 px-6 py-3"
                style={{
                  background: "oklch(0.09 0.015 265)",
                  borderBottom: "1px solid oklch(1 0 0 / 8%)",
                }}
              >
                {[["Variable", "col-span-4"], ["Required", "col-span-2"], ["Description", "col-span-6"]].map(([h, cls]) => (
                  <span
                    key={h}
                    className={`text-xs tracking-widest uppercase ${cls}`}
                    style={{ fontFamily: "'DM Mono', monospace", color: "oklch(0.40 0.01 80)" }}
                  >
                    {h}
                  </span>
                ))}
              </div>

              {envVars.map((env, i) => (
                <motion.div
                  key={env.var}
                  initial={{ opacity: 0 }}
                  whileInView={{ opacity: 1 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.06 }}
                  className="grid grid-cols-12 px-6 py-4 items-center transition-colors duration-150"
                  style={{
                    borderBottom: i < envVars.length - 1 ? "1px solid oklch(1 0 0 / 5%)" : "none",
                    background: i % 2 === 0 ? "oklch(0.13 0.015 265)" : "oklch(0.115 0.015 265)",
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "oklch(0.16 0.015 265)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = i % 2 === 0 ? "oklch(0.13 0.015 265)" : "oklch(0.115 0.015 265)"; }}
                >
                  <span
                    className="col-span-4 text-xs"
                    style={{ color: "oklch(0.75 0.18 70)", fontFamily: "'DM Mono', monospace" }}
                  >
                    {env.var}
                  </span>
                  <span className="col-span-2">
                    <span
                      className="px-2 py-0.5 rounded-sm text-xs"
                      style={{
                        background: env.required ? "oklch(0.75 0.18 70 / 0.1)" : "oklch(1 0 0 / 0.04)",
                        border: `1px solid ${env.required ? "oklch(0.75 0.18 70 / 0.3)" : "oklch(1 0 0 / 0.08)"}`,
                        color: env.required ? "oklch(0.75 0.18 70)" : "oklch(0.45 0.01 80)",
                        fontFamily: "'DM Mono', monospace",
                        fontSize: "0.65rem",
                      }}
                    >
                      {env.required ? "Required" : "Optional"}
                    </span>
                  </span>
                  <span
                    className="col-span-6 text-sm"
                    style={{ color: "oklch(0.55 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}
                  >
                    {env.desc}
                  </span>
                </motion.div>
              ))}
            </div>
          </FadeUp>

          <FadeUp delay={0.3}>
            <div
              className="mt-6 p-5 rounded-sm"
              style={{
                background: "oklch(0.09 0.015 265)",
                border: "1px solid oklch(1 0 0 / 8%)",
                fontFamily: "'DM Mono', monospace",
                fontSize: "0.75rem",
              }}
            >
              <div style={{ color: "oklch(0.40 0.01 80)" }}># Setup</div>
              <div style={{ color: "oklch(0.93 0.01 80)" }}>cp .env.example .env</div>
              <div style={{ color: "oklch(0.40 0.01 80)" }}># Edit .env with your API keys</div>
              <div style={{ color: "oklch(0.93 0.01 80)" }}>python app.py</div>
              <div style={{ color: "oklch(0.40 0.01 80)" }}># API available at http://localhost:8000</div>
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
