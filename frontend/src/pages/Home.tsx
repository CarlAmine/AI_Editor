/* ============================================================
   Home Page — Cinematic Dark Editorial
   Hero + Quick Features + Pipeline Preview + CTA
   ============================================================ */

import { motion, useScroll, useTransform } from "framer-motion";
import { useRef } from "react";
import { Link } from "wouter";
import { ArrowRight, Play, Zap, Brain, Film, Upload, ChevronDown } from "lucide-react";

const HERO_BG = "https://d2xsxph8kpxj0f.cloudfront.net/310519663430434203/9uG5qr437XNp5huy95qtns/hero-bg-U2jyRmUNZooPfRa34tY6Z9.webp";
const PIPELINE_IMG = "https://d2xsxph8kpxj0f.cloudfront.net/310519663430434203/9uG5qr437XNp5huy95qtns/pipeline-visual-eD65tg8hyrjreTHTQV2tKg.webp";

const quickFeatures = [
  {
    icon: Brain,
    title: "AI Edit Planning",
    desc: "Groq LLM converts your natural language brief into a structured edit plan JSON.",
    color: "oklch(0.75 0.18 70)",
  },
  {
    icon: Film,
    title: "Scene Analysis",
    desc: "SceneDetect + EasyOCR + PaddleOCR extract structure, timing, and text from reference videos.",
    color: "oklch(0.55 0.22 255)",
  },
  {
    icon: Zap,
    title: "Cloud Rendering",
    desc: "Shotstack assembles your timeline and renders a polished output in the cloud.",
    color: "oklch(0.75 0.18 70)",
  },
  {
    icon: Upload,
    title: "One-Click Publish",
    desc: "OAuth 2.0 YouTube integration — from render to published Short in minutes.",
    color: "oklch(0.55 0.22 255)",
  },
];

const pipelineSteps = [
  { num: "01", label: "Brief", desc: "Natural language input" },
  { num: "02", label: "Analyze", desc: "Scene & OCR detection" },
  { num: "03", label: "Plan", desc: "LLM edit plan JSON" },
  { num: "04", label: "Render", desc: "Shotstack cloud" },
  { num: "05", label: "Export", desc: "YouTube publish" },
];

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

export default function Home() {
  const heroRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: heroRef, offset: ["start start", "end start"] });
  const heroY = useTransform(scrollYProgress, [0, 1], ["0%", "30%"]);
  const heroOpacity = useTransform(scrollYProgress, [0, 0.8], [1, 0]);

  return (
    <div className="min-h-screen">
      {/* ── HERO ── */}
      <section
        ref={heroRef}
        className="relative min-h-screen flex flex-col items-center justify-center overflow-hidden"
      >
        {/* Parallax background */}
        <motion.div
          className="absolute inset-0 z-0"
          style={{ y: heroY }}
        >
          <img
            src={HERO_BG}
            alt="AI Editor hero"
            className="w-full h-full object-cover"
            style={{ filter: "brightness(0.45) saturate(1.2)" }}
          />
          {/* Gradient overlays */}
          <div
            className="absolute inset-0"
            style={{
              background: "linear-gradient(to bottom, oklch(0.09 0.015 265 / 0.3) 0%, oklch(0.09 0.015 265 / 0.6) 60%, oklch(0.09 0.015 265) 100%)",
            }}
          />
          {/* Amber vignette */}
          <div
            className="absolute inset-0"
            style={{
              background: "radial-gradient(ellipse at 30% 50%, oklch(0.75 0.18 70 / 0.08) 0%, transparent 60%)",
            }}
          />
        </motion.div>

        {/* Film grain overlay */}
        <div
          className="absolute inset-0 z-1 opacity-30 pointer-events-none"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.08'/%3E%3C/svg%3E")`,
            backgroundSize: "256px 256px",
          }}
        />

        {/* Hero content */}
        <motion.div
          className="relative z-10 text-center px-6 max-w-5xl mx-auto"
          style={{ opacity: heroOpacity }}
        >
          {/* Badge */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full mb-8"
            style={{
              border: "1px solid oklch(0.55 0.22 255 / 0.4)",
              background: "oklch(0.55 0.22 255 / 0.08)",
            }}
          >
            <div
              className="w-1.5 h-1.5 rounded-full"
              style={{ background: "oklch(0.55 0.22 255)", boxShadow: "0 0 6px oklch(0.55 0.22 255)" }}
            />
            <span
              className="text-xs tracking-widest uppercase"
              style={{ fontFamily: "'DM Mono', monospace", color: "oklch(0.55 0.22 255)" }}
            >
              Open Source · FastAPI + React
            </span>
          </motion.div>

          {/* Main headline */}
          <motion.h1
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.35 }}
            className="text-7xl md:text-9xl lg:text-[10rem] leading-none tracking-wider mb-6"
            style={{
              fontFamily: "'Bebas Neue', sans-serif",
              background: "linear-gradient(160deg, oklch(0.95 0.01 80) 0%, oklch(0.75 0.18 70) 50%, oklch(0.93 0.01 80) 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            AI EDITOR
          </motion.h1>

          {/* Subtitle */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.5 }}
            className="text-lg md:text-xl max-w-2xl mx-auto mb-10 leading-relaxed"
            style={{ color: "oklch(0.72 0.01 80)", fontFamily: "'DM Sans', sans-serif", fontWeight: 300 }}
          >
            AI-assisted video editing pipeline — from reference analysis to rendered output,
            with full-stack orchestration, Shorts conversion, and one-click publishing.
          </motion.p>

          {/* CTA buttons */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.65 }}
            className="flex flex-wrap items-center justify-center gap-4"
          >
            <Link href="/workspace">
              <button
                className="flex items-center gap-2 px-7 py-3.5 text-sm font-semibold rounded-sm transition-all duration-300"
                style={{
                  background: "oklch(0.75 0.18 70)",
                  color: "oklch(0.09 0.015 265)",
                  fontFamily: "'DM Sans', sans-serif",
                  letterSpacing: "0.05em",
                  boxShadow: "0 0 30px oklch(0.75 0.18 70 / 0.3)",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.boxShadow = "0 0 50px oklch(0.75 0.18 70 / 0.5)";
                  e.currentTarget.style.transform = "translateY(-2px)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.boxShadow = "0 0 30px oklch(0.75 0.18 70 / 0.3)";
                  e.currentTarget.style.transform = "translateY(0)";
                }}
              >
                Try AI Editor
                <ArrowRight size={16} />
              </button>
            </Link>
            <Link href="/features">
              <button
                className="flex items-center gap-2 px-7 py-3.5 text-sm font-semibold rounded-sm transition-all duration-300"
                style={{
                  border: "1px solid oklch(1 0 0 / 20%)",
                  color: "oklch(0.85 0.01 80)",
                  fontFamily: "'DM Sans', sans-serif",
                  letterSpacing: "0.05em",
                  background: "oklch(1 0 0 / 0.03)",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "oklch(1 0 0 / 0.08)";
                  e.currentTarget.style.borderColor = "oklch(1 0 0 / 0.35)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "oklch(1 0 0 / 0.03)";
                  e.currentTarget.style.borderColor = "oklch(1 0 0 / 20%)";
                }}
              >
                Explore Features
              </button>
            </Link>
            <a
              href="https://github.com/CarlAmine/AI_Editor"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 px-7 py-3.5 text-sm font-semibold rounded-sm transition-all duration-300"
              style={{
                border: "1px solid oklch(1 0 0 / 20%)",
                color: "oklch(0.85 0.01 80)",
                fontFamily: "'DM Sans', sans-serif",
                letterSpacing: "0.05em",
                background: "oklch(1 0 0 / 0.03)",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "oklch(1 0 0 / 0.08)";
                e.currentTarget.style.borderColor = "oklch(1 0 0 / 0.35)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "oklch(1 0 0 / 0.03)";
                e.currentTarget.style.borderColor = "oklch(1 0 0 / 0.20)";
              }}
            >
              <Play size={14} />
              View on GitHub
            </a>
          </motion.div>
        </motion.div>

        {/* Scroll indicator */}
        <motion.div
          className="absolute bottom-8 left-1/2 -translate-x-1/2 z-10 flex flex-col items-center gap-2"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.2 }}
        >
          <span
            className="text-xs tracking-widest uppercase"
            style={{ fontFamily: "'DM Mono', monospace", color: "oklch(0.45 0.01 80)" }}
          >
            Scroll
          </span>
          <motion.div
            animate={{ y: [0, 6, 0] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          >
            <ChevronDown size={16} style={{ color: "oklch(0.45 0.01 80)" }} />
          </motion.div>
        </motion.div>
      </section>

      {/* ── PIPELINE STRIP ── */}
      <section className="py-16 overflow-hidden" style={{ background: "oklch(0.11 0.015 265)" }}>
        <div className="container mx-auto px-6 max-w-7xl">
          <FadeUp>
            <div className="flex items-center gap-4 mb-10">
              <div className="amber-divider flex-1" />
              <span className="section-number">Pipeline Flow</span>
              <div className="amber-divider flex-1" />
            </div>
          </FadeUp>

          <div className="flex flex-col md:flex-row items-center gap-0">
            {pipelineSteps.map((step, i) => (
              <FadeUp key={step.num} delay={i * 0.1}>
                <div className="flex items-center">
                  <div className="flex flex-col items-center text-center px-6 py-4">
                    <span
                      className="text-3xl mb-2"
                      style={{
                        fontFamily: "'DM Mono', monospace",
                        color: "oklch(0.75 0.18 70)",
                        fontWeight: 300,
                      }}
                    >
                      {step.num}
                    </span>
                    <span
                      className="text-base font-semibold mb-1"
                      style={{ fontFamily: "'Bebas Neue', sans-serif", color: "oklch(0.93 0.01 80)", letterSpacing: "0.1em" }}
                    >
                      {step.label}
                    </span>
                    <span
                      className="text-xs"
                      style={{ color: "oklch(0.50 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}
                    >
                      {step.desc}
                    </span>
                  </div>
                  {i < pipelineSteps.length - 1 && (
                    <div className="hidden md:flex items-center">
                      <motion.div
                        className="h-px"
                        style={{
                          width: "40px",
                          background: "linear-gradient(90deg, oklch(0.75 0.18 70 / 0.6), oklch(0.55 0.22 255 / 0.6))",
                        }}
                        initial={{ scaleX: 0 }}
                        whileInView={{ scaleX: 1 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.4, delay: i * 0.1 + 0.3 }}
                      />
                      <div
                        className="w-1.5 h-1.5 rounded-full"
                        style={{ background: "oklch(0.55 0.22 255)", boxShadow: "0 0 6px oklch(0.55 0.22 255)" }}
                      />
                    </div>
                  )}
                </div>
              </FadeUp>
            ))}
          </div>
        </div>
      </section>

      {/* ── QUICK FEATURES ── */}
      <section className="py-24">
        <div className="container mx-auto px-6 max-w-7xl">
          <FadeUp>
            <div className="mb-16">
              <span className="section-number block mb-3">01 — Core Capabilities</span>
              <h2
                className="text-5xl md:text-7xl"
                style={{
                  fontFamily: "'Bebas Neue', sans-serif",
                  color: "oklch(0.93 0.01 80)",
                  letterSpacing: "0.02em",
                }}
              >
                Not Just a Wrapper
              </h2>
              <p
                className="mt-4 max-w-xl text-base leading-relaxed"
                style={{ color: "oklch(0.55 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}
              >
                AI Editor integrates computer vision, LLM planning, cloud rendering, and OAuth publishing
                into a cohesive, production-ready pipeline.
              </p>
            </div>
          </FadeUp>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {quickFeatures.map((feat, i) => {
              const Icon = feat.icon;
              return (
                <FadeUp key={feat.title} delay={i * 0.1}>
                  <div
                    className="card-lift p-8 rounded-sm"
                    style={{
                      background: "oklch(0.13 0.015 265)",
                      border: "1px solid oklch(1 0 0 / 6%)",
                    }}
                  >
                    <div
                      className="w-10 h-10 rounded-sm flex items-center justify-center mb-5"
                      style={{
                        background: `${feat.color.replace(")", " / 0.12)")}`,
                        border: `1px solid ${feat.color.replace(")", " / 0.3)")}`,
                      }}
                    >
                      <Icon size={18} style={{ color: feat.color }} />
                    </div>
                    <h3
                      className="text-2xl mb-3"
                      style={{ fontFamily: "'Bebas Neue', sans-serif", color: "oklch(0.93 0.01 80)", letterSpacing: "0.05em" }}
                    >
                      {feat.title}
                    </h3>
                    <p
                      className="text-sm leading-relaxed"
                      style={{ color: "oklch(0.55 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}
                    >
                      {feat.desc}
                    </p>
                  </div>
                </FadeUp>
              );
            })}
          </div>

          <FadeUp delay={0.4}>
            <div className="mt-8 text-center">
              <Link href="/features">
                <button
                  className="inline-flex items-center gap-2 px-6 py-3 text-sm font-medium rounded-sm transition-all duration-200"
                  style={{
                    color: "oklch(0.75 0.18 70)",
                    border: "1px solid oklch(0.75 0.18 70 / 0.3)",
                    background: "oklch(0.75 0.18 70 / 0.05)",
                    fontFamily: "'DM Sans', sans-serif",
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = "oklch(0.75 0.18 70 / 0.12)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = "oklch(0.75 0.18 70 / 0.05)"; }}
                >
                  View all features
                  <ArrowRight size={14} />
                </button>
              </Link>
            </div>
          </FadeUp>
        </div>
      </section>

      {/* ── PIPELINE VISUAL ── */}
      <section className="py-24" style={{ background: "oklch(0.11 0.015 265)" }}>
        <div className="container mx-auto px-6 max-w-7xl">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
            <FadeUp>
              <div>
                <span className="section-number block mb-3">02 — Architecture</span>
                <h2
                  className="text-5xl md:text-6xl mb-6"
                  style={{ fontFamily: "'Bebas Neue', sans-serif", color: "oklch(0.93 0.01 80)", letterSpacing: "0.02em" }}
                >
                  Multi-Stage Pipeline Orchestration
                </h2>
                <p
                  className="text-base leading-relaxed mb-8"
                  style={{ color: "oklch(0.55 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}
                >
                  The pipeline runner coordinates ordered stages with state transitions, retry logic,
                  and per-job artifact isolation. Every stage is independently testable and observable.
                </p>
                <div className="space-y-3">
                  {[
                    "Asset download via yt-dlp & Google Drive",
                    "Timeline assembly with overlay planning",
                    "Shotstack render submission & polling",
                    "Artifact storage per job ID",
                  ].map((item, i) => (
                    <motion.div
                      key={item}
                      initial={{ opacity: 0, x: -20 }}
                      whileInView={{ opacity: 1, x: 0 }}
                      viewport={{ once: true }}
                      transition={{ delay: i * 0.1 }}
                      className="flex items-center gap-3"
                    >
                      <div
                        className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                        style={{ background: "oklch(0.75 0.18 70)", boxShadow: "0 0 6px oklch(0.75 0.18 70 / 0.6)" }}
                      />
                      <span
                        className="text-sm"
                        style={{ color: "oklch(0.65 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}
                      >
                        {item}
                      </span>
                    </motion.div>
                  ))}
                </div>
                <div className="mt-8">
                  <Link href="/architecture">
                    <button
                      className="inline-flex items-center gap-2 px-6 py-3 text-sm font-medium rounded-sm transition-all duration-200"
                      style={{
                        color: "oklch(0.75 0.18 70)",
                        border: "1px solid oklch(0.75 0.18 70 / 0.3)",
                        background: "oklch(0.75 0.18 70 / 0.05)",
                        fontFamily: "'DM Sans', sans-serif",
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = "oklch(0.75 0.18 70 / 0.12)"; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = "oklch(0.75 0.18 70 / 0.05)"; }}
                    >
                      View Architecture
                      <ArrowRight size={14} />
                    </button>
                  </Link>
                </div>
              </div>
            </FadeUp>

            <FadeUp delay={0.2}>
              <div className="relative">
                <img
                  src={PIPELINE_IMG}
                  alt="Pipeline visualization"
                  className="w-full rounded-sm"
                  style={{
                    border: "1px solid oklch(1 0 0 / 8%)",
                    boxShadow: "0 30px 80px oklch(0 0 0 / 0.5), 0 0 40px oklch(0.75 0.18 70 / 0.08)",
                  }}
                />
                {/* Amber corner accent */}
                <div
                  className="absolute top-0 left-0 w-8 h-8"
                  style={{
                    borderTop: "2px solid oklch(0.75 0.18 70)",
                    borderLeft: "2px solid oklch(0.75 0.18 70)",
                  }}
                />
                <div
                  className="absolute bottom-0 right-0 w-8 h-8"
                  style={{
                    borderBottom: "2px solid oklch(0.75 0.18 70)",
                    borderRight: "2px solid oklch(0.75 0.18 70)",
                  }}
                />
              </div>
            </FadeUp>
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="py-32 text-center relative overflow-hidden">
        <div
          className="absolute inset-0"
          style={{
            background: "radial-gradient(ellipse at 50% 50%, oklch(0.75 0.18 70 / 0.06) 0%, transparent 70%)",
          }}
        />
        <div className="container mx-auto px-6 max-w-3xl relative z-10">
          <FadeUp>
            <h2
              className="text-6xl md:text-8xl mb-6"
              style={{ fontFamily: "'Bebas Neue', sans-serif", color: "oklch(0.93 0.01 80)", letterSpacing: "0.02em" }}
            >
              Ready to Build?
            </h2>
            <p
              className="text-base leading-relaxed mb-10"
              style={{ color: "oklch(0.55 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}
            >
              Clone the repo, configure your API keys, and have a fully automated video editing
              pipeline running in minutes.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-4">
              <Link href="/docs">
                <button
                  className="flex items-center gap-2 px-8 py-4 text-sm font-semibold rounded-sm transition-all duration-300"
                  style={{
                    background: "oklch(0.75 0.18 70)",
                    color: "oklch(0.09 0.015 265)",
                    fontFamily: "'DM Sans', sans-serif",
                    letterSpacing: "0.05em",
                    boxShadow: "0 0 30px oklch(0.75 0.18 70 / 0.3)",
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.boxShadow = "0 0 50px oklch(0.75 0.18 70 / 0.5)"; e.currentTarget.style.transform = "translateY(-2px)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.boxShadow = "0 0 30px oklch(0.75 0.18 70 / 0.3)"; e.currentTarget.style.transform = "translateY(0)"; }}
                >
                  Quick Start Guide
                  <ArrowRight size={16} />
                </button>
              </Link>
              <a
                href="https://github.com/CarlAmine/AI_Editor"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 px-8 py-4 text-sm font-semibold rounded-sm transition-all duration-300"
                style={{
                  border: "1px solid oklch(1 0 0 / 20%)",
                  color: "oklch(0.85 0.01 80)",
                  fontFamily: "'DM Sans', sans-serif",
                  letterSpacing: "0.05em",
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "oklch(1 0 0 / 0.05)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
              >
                Star on GitHub
              </a>
            </div>
          </FadeUp>
        </div>
      </section>

      {/* Footer */}
      <footer
        className="py-8 text-center"
        style={{ borderTop: "1px solid oklch(1 0 0 / 6%)" }}
      >
        <p
          className="text-xs tracking-widest uppercase"
          style={{ fontFamily: "'DM Mono', monospace", color: "oklch(0.35 0.01 80)" }}
        >
          AI Editor · Open Source · MIT License · by{" "}
          <a
            href="https://github.com/CarlAmine"
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: "oklch(0.75 0.18 70)" }}
          >
            CarlAmine
          </a>
        </p>
      </footer>
    </div>
  );
}
