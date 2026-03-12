/* ============================================================
   About Page — Cinematic Dark Editorial
   Project story, creator, mission, and open source info
   ============================================================ */

import { motion } from "framer-motion";
import { Github, Star, GitFork, Code2, Heart } from "lucide-react";

const AI_BRAIN = "https://d2xsxph8kpxj0f.cloudfront.net/310519663430434203/9uG5qr437XNp5huy95qtns/ai-brain-EXVBxYbMn3VQPenAmPAsJL.webp";

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

const values = [
  {
    title: "Not a Wrapper",
    desc: "AI Editor goes beyond simple LLM API calls. It integrates computer vision, structured planning, cloud rendering, and OAuth publishing into a cohesive system.",
    icon: Code2,
  },
  {
    title: "Production-Ready",
    desc: "Built with FastAPI, Docker, pytest coverage, and a structured pipeline runner with state machines and retry logic — not a prototype.",
    icon: Star,
  },
  {
    title: "Open Source",
    desc: "MIT licensed and fully open. Contributions are welcome — see CONTRIBUTING.md for guidelines on adding stages, integrations, or frontend features.",
    icon: Heart,
  },
];

export default function About() {
  return (
    <div className="min-h-screen pt-24">
      {/* ── PAGE HEADER ── */}
      <section className="py-20 relative overflow-hidden">
        <div
          className="absolute inset-0"
          style={{
            background: "radial-gradient(ellipse at 70% 50%, oklch(0.75 0.18 70 / 0.05) 0%, transparent 60%)",
          }}
        />
        <div className="container mx-auto px-6 max-w-7xl relative z-10">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
            <div>
              <FadeUp>
                <span className="section-number block mb-4">About the Project</span>
                <h1
                  className="text-7xl md:text-9xl leading-none mb-8"
                  style={{
                    fontFamily: "'Bebas Neue', sans-serif",
                    background: "linear-gradient(160deg, oklch(0.95 0.01 80) 0%, oklch(0.75 0.18 70) 100%)",
                    WebkitBackgroundClip: "text",
                    WebkitTextFillColor: "transparent",
                    backgroundClip: "text",
                  }}
                >
                  What Is AI Editor?
                </h1>
              </FadeUp>
              <FadeUp delay={0.15}>
                <p
                  className="text-base leading-relaxed mb-6"
                  style={{ color: "oklch(0.60 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}
                >
                  AI Editor is a multi-stage media pipeline that accepts a{" "}
                  <em style={{ color: "oklch(0.75 0.18 70)" }}>reference video</em> and a set of{" "}
                  <em style={{ color: "oklch(0.75 0.18 70)" }}>source clips</em>, uses AI analysis to
                  understand structure and style, builds a stage-based edit plan, renders a polished
                  output via the Shotstack API, and optionally converts the result to a vertical Short
                  and publishes to YouTube.
                </p>
                <p
                  className="text-base leading-relaxed"
                  style={{ color: "oklch(0.60 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}
                >
                  It is <strong style={{ color: "oklch(0.93 0.01 80)" }}>not a simple wrapper</strong>{" "}
                  around an LLM. It integrates computer-vision based video analysis, AI-driven edit
                  planning, a structured multi-stage pipeline runner, Shotstack rendering, and a React
                  frontend with job status tracking and Google OAuth.
                </p>
              </FadeUp>
              <FadeUp delay={0.3}>
                <div className="flex flex-wrap gap-4 mt-8">
                  <a
                    href="https://github.com/CarlAmine/AI_Editor"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 px-5 py-2.5 text-sm font-medium rounded-sm transition-all duration-200"
                    style={{
                      background: "oklch(0.75 0.18 70)",
                      color: "oklch(0.09 0.015 265)",
                      fontFamily: "'DM Sans', sans-serif",
                      boxShadow: "0 0 20px oklch(0.75 0.18 70 / 0.25)",
                    }}
                  >
                    <Github size={15} />
                    View Repository
                  </a>
                  <a
                    href="https://github.com/CarlAmine/AI_Editor/blob/main/CONTRIBUTING.md"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 px-5 py-2.5 text-sm font-medium rounded-sm transition-all duration-200"
                    style={{
                      border: "1px solid oklch(1 0 0 / 15%)",
                      color: "oklch(0.65 0.01 80)",
                      fontFamily: "'DM Sans', sans-serif",
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "oklch(1 0 0 / 0.05)"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                  >
                    <GitFork size={15} />
                    Contributing
                  </a>
                </div>
              </FadeUp>
            </div>

            <FadeUp delay={0.2}>
              <div className="relative">
                <img
                  src={AI_BRAIN}
                  alt="AI neural network visualization"
                  className="w-full rounded-sm"
                  style={{
                    border: "1px solid oklch(1 0 0 / 8%)",
                    boxShadow: "0 30px 80px oklch(0 0 0 / 0.5), 0 0 60px oklch(0.75 0.18 70 / 0.1)",
                  }}
                />
                <div
                  className="absolute top-0 left-0 w-8 h-8"
                  style={{ borderTop: "2px solid oklch(0.75 0.18 70)", borderLeft: "2px solid oklch(0.75 0.18 70)" }}
                />
                <div
                  className="absolute bottom-0 right-0 w-8 h-8"
                  style={{ borderBottom: "2px solid oklch(0.55 0.22 255)", borderRight: "2px solid oklch(0.55 0.22 255)" }}
                />
              </div>
            </FadeUp>
          </div>
        </div>
      </section>

      {/* ── AMBER DIVIDER ── */}
      <div className="container mx-auto px-6 max-w-7xl">
        <div className="amber-divider" />
      </div>

      {/* ── VALUES ── */}
      <section className="py-24">
        <div className="container mx-auto px-6 max-w-7xl">
          <FadeUp>
            <span className="section-number block mb-3">Design Philosophy</span>
            <h2
              className="text-5xl md:text-7xl mb-16"
              style={{ fontFamily: "'Bebas Neue', sans-serif", color: "oklch(0.93 0.01 80)", letterSpacing: "0.02em" }}
            >
              Built with Purpose
            </h2>
          </FadeUp>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {values.map((val, i) => {
              const Icon = val.icon;
              return (
                <FadeUp key={val.title} delay={i * 0.12}>
                  <div
                    className="p-8 rounded-sm card-lift"
                    style={{
                      background: "oklch(0.13 0.015 265)",
                      border: "1px solid oklch(1 0 0 / 6%)",
                    }}
                  >
                    <div
                      className="w-10 h-10 rounded-sm flex items-center justify-center mb-5"
                      style={{
                        background: "oklch(0.75 0.18 70 / 0.1)",
                        border: "1px solid oklch(0.75 0.18 70 / 0.3)",
                      }}
                    >
                      <Icon size={18} style={{ color: "oklch(0.75 0.18 70)" }} />
                    </div>
                    <h3
                      className="text-2xl mb-3"
                      style={{ fontFamily: "'Bebas Neue', sans-serif", color: "oklch(0.93 0.01 80)", letterSpacing: "0.05em" }}
                    >
                      {val.title}
                    </h3>
                    <p
                      className="text-sm leading-relaxed"
                      style={{ color: "oklch(0.55 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}
                    >
                      {val.desc}
                    </p>
                  </div>
                </FadeUp>
              );
            })}
          </div>
        </div>
      </section>

      {/* ── CREATOR ── */}
      <section className="py-24" style={{ background: "oklch(0.11 0.015 265)" }}>
        <div className="container mx-auto px-6 max-w-7xl">
          <div className="max-w-2xl">
            <FadeUp>
              <span className="section-number block mb-3">Creator</span>
              <h2
                className="text-5xl md:text-6xl mb-6"
                style={{ fontFamily: "'Bebas Neue', sans-serif", color: "oklch(0.93 0.01 80)", letterSpacing: "0.02em" }}
              >
                CarlAmine
              </h2>
              <p
                className="text-base leading-relaxed mb-8"
                style={{ color: "oklch(0.55 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}
              >
                AI Editor is an open-source project by CarlAmine, built to explore the intersection of
                AI, computer vision, and video production automation. The project demonstrates how
                modern LLMs, cloud APIs, and structured pipelines can work together to automate
                creative workflows.
              </p>
              <a
                href="https://github.com/CarlAmine"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 text-sm font-medium transition-colors duration-200"
                style={{ color: "oklch(0.75 0.18 70)", fontFamily: "'DM Sans', sans-serif" }}
              >
                <Github size={16} />
                github.com/CarlAmine
              </a>
            </FadeUp>
          </div>
        </div>
      </section>

      {/* ── LICENSE ── */}
      <section className="py-16">
        <div className="container mx-auto px-6 max-w-7xl">
          <FadeUp>
            <div
              className="p-8 rounded-sm"
              style={{
                background: "oklch(0.13 0.015 265)",
                border: "1px solid oklch(0.75 0.18 70 / 0.15)",
              }}
            >
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                <div>
                  <h3
                    className="text-3xl mb-2"
                    style={{ fontFamily: "'Bebas Neue', sans-serif", color: "oklch(0.93 0.01 80)", letterSpacing: "0.05em" }}
                  >
                    MIT License
                  </h3>
                  <p
                    className="text-sm"
                    style={{ color: "oklch(0.55 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}
                  >
                    Free to use, modify, and distribute. See LICENSE for full terms.
                  </p>
                </div>
                <a
                  href="https://github.com/CarlAmine/AI_Editor/blob/main/LICENSE"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 px-5 py-2.5 text-sm font-medium rounded-sm transition-all duration-200 flex-shrink-0"
                  style={{
                    border: "1px solid oklch(0.75 0.18 70 / 0.3)",
                    color: "oklch(0.75 0.18 70)",
                    fontFamily: "'DM Sans', sans-serif",
                    background: "oklch(0.75 0.18 70 / 0.05)",
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "oklch(0.75 0.18 70 / 0.12)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = "oklch(0.75 0.18 70 / 0.05)"; }}
                >
                  View License
                </a>
              </div>
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
