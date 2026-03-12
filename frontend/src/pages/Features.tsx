/* ============================================================
   Features Page — Cinematic Dark Editorial
   All 8 key features with detailed descriptions and visuals
   ============================================================ */

import { motion } from "framer-motion";
import { Film, Brain, Layers, Clapperboard, Scissors, Upload, HardDrive, TestTube } from "lucide-react";

const VIDEO_EDITING_UI = "https://d2xsxph8kpxj0f.cloudfront.net/310519663430434203/9uG5qr437XNp5huy95qtns/video-editing-ui-7cZo4UVq5DqSJdWuEupihE.webp";
const YOUTUBE_CLOUD = "https://d2xsxph8kpxj0f.cloudfront.net/310519663430434203/9uG5qr437XNp5huy95qtns/youtube-cloud-m94NFynCqogTHv3fJNLHSv.webp";

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

const features = [
  {
    num: "01",
    icon: Film,
    title: "Reference Video Analysis",
    subtitle: "Scene detection · OCR extraction · Structure parsing",
    desc: "The Analyzer module processes your reference video using SceneDetect for shot boundary detection, combined with EasyOCR and PaddleOCR for text extraction from key frames. The result is a structured map of scenes, timing, and text overlays.",
    details: ["SceneDetect-based shot boundary detection", "EasyOCR + PaddleOCR text extraction", "Frame-level structure analysis", "OCR-extracted timeline metadata"],
    color: "oklch(0.75 0.18 70)",
    file: "ai_editor/analyzer.py",
  },
  {
    num: "02",
    icon: Brain,
    title: "AI Edit Planning",
    subtitle: "Groq LLM · Conversational brief builder · Structured JSON output",
    desc: "The chatbot interface uses Groq's LLM to power a conversational brief builder. You describe your vision in natural language, and the AI refines it into a machine-readable edit plan JSON that drives the entire pipeline.",
    details: ["Groq API integration", "Conversational brief refinement", "Structured edit plan JSON output", "Custom planner + LLM hybrid"],
    color: "oklch(0.55 0.22 255)",
    file: "ai_editor/chatbot_interface.py",
  },
  {
    num: "03",
    icon: Layers,
    title: "Stage-Based Pipeline",
    subtitle: "Ordered stages · State persistence · Per-job isolation",
    desc: "The pipeline runner (pipeline/runner.py, ~60KB) coordinates ordered stages with state transitions, retry logic, and per-job artifact isolation. Each job gets its own state machine and artifact directory.",
    details: ["Ordered stage execution", "Per-job state machine", "Retry logic on failure", "Artifact path isolation per job"],
    color: "oklch(0.75 0.18 70)",
    file: "pipeline/runner.py",
  },
  {
    num: "04",
    icon: Clapperboard,
    title: "Shotstack Rendering",
    subtitle: "Timeline assembly · Cloud render · Artifact storage",
    desc: "The Editor module programmatically constructs Shotstack render specs from clip lists, overlays, and timing metadata. Shotstack renders the timeline in the cloud and returns a video URL, which is stored as a job artifact.",
    details: ["Shotstack SDK integration", "Programmatic timeline construction", "Cloud render submission & polling", "Render artifact storage"],
    color: "oklch(0.55 0.22 255)",
    file: "ai_editor/editor.py",
  },
  {
    num: "05",
    icon: Scissors,
    title: "Shorts Conversion",
    subtitle: "16:9 → 9:16 · Reframe · Post-process",
    desc: "Automatic conversion of landscape renders to vertical Shorts format. The converter handles 16:9 to 9:16 crop, intelligent reframing to keep subjects centered, and post-processing for vertical delivery.",
    details: ["16:9 → 9:16 aspect ratio conversion", "Intelligent subject reframing", "Post-processing pipeline", "Vertical delivery optimization"],
    color: "oklch(0.75 0.18 70)",
    file: "ai_editor/youtube_clipper.py",
  },
  {
    num: "06",
    icon: Upload,
    title: "YouTube Publishing",
    subtitle: "OAuth 2.0 · Metadata · Direct publish",
    desc: "Full YouTube Data API v3 integration with OAuth 2.0 authentication. Set video metadata, privacy settings, and publish directly from the pipeline. The uploader handles token refresh and credential management.",
    details: ["YouTube Data API v3", "OAuth 2.0 authentication flow", "Video metadata management", "Token refresh & credential storage"],
    color: "oklch(0.55 0.22 255)",
    file: "ai_editor/youtube_uploader.py",
  },
  {
    num: "07",
    icon: HardDrive,
    title: "Google Drive Ingestion",
    subtitle: "Service account · OAuth · Asset retrieval",
    desc: "Flexible asset ingestion from Google Drive using either service account credentials or OAuth-based authentication. Combined with yt-dlp for YouTube clip extraction, the downloader handles all asset sourcing.",
    details: ["Google Drive API integration", "Service account + OAuth support", "yt-dlp YouTube clip extraction", "Folder-based asset organization"],
    color: "oklch(0.75 0.18 70)",
    file: "ai_editor/downloader.py",
  },
  {
    num: "08",
    icon: TestTube,
    title: "Unit Test Coverage",
    subtitle: "pytest · Normalization · Overlay policy · Text segments",
    desc: "Comprehensive pytest test suites covering timeline normalization and clip boundary logic, overlay scheduling and policy enforcement, and text segment parsing and validation.",
    details: ["test_editor_normalization.py", "test_overlay_policy.py", "test_text_segments.py", "pytest with -v verbose output"],
    color: "oklch(0.55 0.22 255)",
    file: "tests/",
  },
];

export default function Features() {
  return (
    <div className="min-h-screen pt-24">
      {/* ── PAGE HEADER ── */}
      <section className="py-20 relative overflow-hidden">
        <div
          className="absolute inset-0"
          style={{
            background: "radial-gradient(ellipse at 30% 50%, oklch(0.55 0.22 255 / 0.05) 0%, transparent 60%)",
          }}
        />
        <div className="container mx-auto px-6 max-w-7xl relative z-10">
          <FadeUp>
            <span className="section-number block mb-4">Key Features</span>
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
              8 Core Capabilities
            </h1>
            <p
              className="text-base leading-relaxed max-w-xl"
              style={{ color: "oklch(0.55 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}
            >
              Every feature is a production-ready module with clear responsibilities, tested interfaces,
              and documented configuration.
            </p>
          </FadeUp>
        </div>
      </section>

      {/* ── FEATURE SHOWCASE IMAGE ── */}
      <section className="pb-16">
        <div className="container mx-auto px-6 max-w-7xl">
          <FadeUp>
            <div className="relative rounded-sm overflow-hidden">
              <img
                src={VIDEO_EDITING_UI}
                alt="AI Editor video editing interface"
                className="w-full"
                style={{
                  maxHeight: "400px",
                  objectFit: "cover",
                  objectPosition: "center top",
                  filter: "brightness(0.8)",
                }}
              />
              <div
                className="absolute inset-0"
                style={{
                  background: "linear-gradient(to right, oklch(0.09 0.015 265 / 0.8) 0%, transparent 40%, transparent 60%, oklch(0.09 0.015 265 / 0.8) 100%)",
                }}
              />
              <div
                className="absolute inset-0"
                style={{
                  background: "linear-gradient(to bottom, transparent 60%, oklch(0.09 0.015 265) 100%)",
                }}
              />
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="text-center">
                  <span
                    className="text-xs tracking-widest uppercase block mb-2"
                    style={{ fontFamily: "'DM Mono', monospace", color: "oklch(0.75 0.18 70)" }}
                  >
                    AI-Powered
                  </span>
                  <span
                    className="text-4xl md:text-6xl"
                    style={{ fontFamily: "'Bebas Neue', sans-serif", color: "oklch(0.93 0.01 80)", letterSpacing: "0.1em" }}
                  >
                    Video Intelligence
                  </span>
                </div>
              </div>
            </div>
          </FadeUp>
        </div>
      </section>

      {/* ── FEATURES LIST ── */}
      <section className="py-8 pb-24">
        <div className="container mx-auto px-6 max-w-7xl">
          <div className="space-y-8">
            {features.map((feat, i) => {
              const Icon = feat.icon;
              return (
                <FadeUp key={feat.num} delay={i * 0.05}>
                  <div
                    className="p-8 md:p-10 rounded-sm card-lift"
                    style={{
                      background: "oklch(0.13 0.015 265)",
                      border: "1px solid oklch(1 0 0 / 6%)",
                    }}
                  >
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                      {/* Left: number + icon + title */}
                      <div className="flex flex-col">
                        <div className="flex items-start gap-4 mb-4">
                          <span
                            className="text-4xl"
                            style={{
                              fontFamily: "'DM Mono', monospace",
                              color: feat.color,
                              fontWeight: 300,
                              lineHeight: 1,
                            }}
                          >
                            {feat.num}
                          </span>
                          <div
                            className="w-10 h-10 rounded-sm flex items-center justify-center flex-shrink-0"
                            style={{
                              background: `${feat.color.replace(")", " / 0.1)")}`,
                              border: `1px solid ${feat.color.replace(")", " / 0.3)")}`,
                            }}
                          >
                            <Icon size={18} style={{ color: feat.color }} />
                          </div>
                        </div>
                        <h3
                          className="text-2xl md:text-3xl mb-2"
                          style={{ fontFamily: "'Bebas Neue', sans-serif", color: "oklch(0.93 0.01 80)", letterSpacing: "0.05em" }}
                        >
                          {feat.title}
                        </h3>
                        <p
                          className="text-xs mb-4"
                          style={{ color: feat.color, fontFamily: "'DM Mono', monospace", letterSpacing: "0.05em" }}
                        >
                          {feat.subtitle}
                        </p>
                        <div
                          className="mt-auto inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-xs"
                          style={{
                            background: "oklch(1 0 0 / 0.04)",
                            border: "1px solid oklch(1 0 0 / 0.08)",
                            fontFamily: "'DM Mono', monospace",
                            color: "oklch(0.50 0.01 80)",
                          }}
                        >
                          <span style={{ color: "oklch(0.75 0.18 70)" }}>~/</span>
                          {feat.file}
                        </div>
                      </div>

                      {/* Middle: description */}
                      <div>
                        <p
                          className="text-sm leading-relaxed"
                          style={{ color: "oklch(0.58 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}
                        >
                          {feat.desc}
                        </p>
                      </div>

                      {/* Right: details list */}
                      <div>
                        <p
                          className="text-xs tracking-widest uppercase mb-3"
                          style={{ fontFamily: "'DM Mono', monospace", color: "oklch(0.40 0.01 80)" }}
                        >
                          Implementation
                        </p>
                        <ul className="space-y-2">
                          {feat.details.map((d, j) => (
                            <motion.li
                              key={d}
                              initial={{ opacity: 0, x: 10 }}
                              whileInView={{ opacity: 1, x: 0 }}
                              viewport={{ once: true }}
                              transition={{ delay: j * 0.06 }}
                              className="flex items-center gap-2.5 text-sm"
                              style={{ color: "oklch(0.62 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}
                            >
                              <div
                                className="w-1 h-1 rounded-full flex-shrink-0"
                                style={{ background: feat.color }}
                              />
                              {d}
                            </motion.li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>
                </FadeUp>
              );
            })}
          </div>
        </div>
      </section>

      {/* ── YOUTUBE SECTION ── */}
      <section className="py-24" style={{ background: "oklch(0.11 0.015 265)" }}>
        <div className="container mx-auto px-6 max-w-7xl">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
            <FadeUp>
              <div className="relative">
                <img
                  src={YOUTUBE_CLOUD}
                  alt="YouTube cloud publishing"
                  className="w-full rounded-sm"
                  style={{
                    border: "1px solid oklch(1 0 0 / 8%)",
                    boxShadow: "0 30px 80px oklch(0 0 0 / 0.5), 0 0 40px oklch(0.55 0.22 255 / 0.08)",
                  }}
                />
                <div
                  className="absolute top-0 left-0 w-8 h-8"
                  style={{ borderTop: "2px solid oklch(0.55 0.22 255)", borderLeft: "2px solid oklch(0.55 0.22 255)" }}
                />
                <div
                  className="absolute bottom-0 right-0 w-8 h-8"
                  style={{ borderBottom: "2px solid oklch(0.75 0.18 70)", borderRight: "2px solid oklch(0.75 0.18 70)" }}
                />
              </div>
            </FadeUp>
            <FadeUp delay={0.2}>
              <div>
                <span className="section-number block mb-3">End-to-End</span>
                <h2
                  className="text-5xl md:text-6xl mb-6"
                  style={{ fontFamily: "'Bebas Neue', sans-serif", color: "oklch(0.93 0.01 80)", letterSpacing: "0.02em" }}
                >
                  From Brief to Published
                </h2>
                <p
                  className="text-base leading-relaxed mb-6"
                  style={{ color: "oklch(0.55 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}
                >
                  The complete pipeline handles everything from your initial brief to a published YouTube
                  video. No manual steps required — the system handles OAuth flows, render polling,
                  format conversion, and metadata management automatically.
                </p>
                <div
                  className="p-4 rounded-sm"
                  style={{
                    background: "oklch(0.09 0.015 265)",
                    border: "1px solid oklch(1 0 0 / 8%)",
                    fontFamily: "'DM Mono', monospace",
                    fontSize: "0.75rem",
                    color: "oklch(0.55 0.01 80)",
                  }}
                >
                  <div style={{ color: "oklch(0.45 0.01 80)" }}># Start a new edit job</div>
                  <div>
                    <span style={{ color: "oklch(0.55 0.22 255)" }}>curl</span>
                    <span style={{ color: "oklch(0.93 0.01 80)" }}> -X POST http://localhost:8000/jobs \</span>
                  </div>
                  <div style={{ color: "oklch(0.93 0.01 80)" }}>  -H 'Content-Type: application/json' \</div>
                  <div>
                    <span style={{ color: "oklch(0.93 0.01 80)" }}>  -d '</span>
                    <span style={{ color: "oklch(0.75 0.18 70)" }}>{`{"reference_url": "...", "brief": "60s highlight reel"}`}</span>
                    <span style={{ color: "oklch(0.93 0.01 80)" }}>'</span>
                  </div>
                </div>
              </div>
            </FadeUp>
          </div>
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
