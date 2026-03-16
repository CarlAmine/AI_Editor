/* ============================================================
   Pipeline Page — Redesigned with 3-step numbered flow
   ============================================================ */
import { useState } from "react";
import { VideoPipelinePanel } from "../components/VideoPipelinePanel";
import { ChatPanel } from "../components/ChatPanel";
import { YouTubePublishStep } from "../components/YouTubePublishStep";
import "./Pipeline.css";

type PipelineResult = {
  success?: boolean;
  url?: string;
  preview_url?: string;
  preview_mode?: string;
  intent_mode?: string;
  project_id?: string;
  user_notice?: string;
  status?: string;
  error?: string;
  render_id?: string;
};

export default function Pipeline() {
  const [briefState, setBriefState] = useState<Record<string, unknown>>({});
  const [renderResult, setRenderResult] = useState<PipelineResult | null>(null);
  const apiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:10000";

  return (
    <div className="min-h-screen pt-24 pipeline-page">
      {/* Hero section */}
      <section className="py-16 relative overflow-hidden">
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse at 30% 50%, oklch(0.75 0.18 70 / 0.08) 0%, transparent 60%)",
          }}
        />
        <div className="container mx-auto px-6 max-w-7xl relative z-10">
          <span className="section-number block mb-4">Pipeline</span>
          <h1
            className="text-6xl md:text-7xl leading-none mb-4"
            style={{
              fontFamily: "'Bebas Neue', sans-serif",
              background:
                "linear-gradient(160deg, oklch(0.95 0.01 80) 0%, oklch(0.75 0.18 70) 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            Functional Pipeline
          </h1>
          <p
            className="text-sm md:text-base max-w-2xl"
            style={{ color: "oklch(0.55 0.01 80)", fontFamily: "'DM Sans', sans-serif" }}
          >
            Run the full pipeline end-to-end: submit sources, render a video, and
            optionally upload to YouTube.
          </p>
        </div>
      </section>

      {/* 3-step flow */}
      <section className="pb-16">
        <div className="container mx-auto px-6 max-w-7xl">

          {/* Steps 1 + 2 side by side on desktop */}
          <div className="pipeline-steps-grid">

            {/* Step 1 */}
            <div className="pipeline-step-wrapper">
              <div className="step-badge">01</div>
              <div className="step-meta">
                <h2 className="step-title">Build Your Edit</h2>
                <p className="step-subtitle">Configure sources, brief, and render settings.</p>
              </div>
              <VideoPipelinePanel
                apiBase={apiBase}
                currentState={briefState}
                onAnalyzerSummary={() => {}}
              />
            </div>

            {/* Step 2 */}
            <div className="pipeline-step-wrapper">
              <div className="step-badge">02</div>
              <div className="step-meta">
                <h2 className="step-title">Brief the Assistant</h2>
                <p className="step-subtitle">Refine your creative brief through conversation.</p>
              </div>
              <ChatPanel
                apiBase={apiBase}
                analyzerOutput=""
                onStateUpdate={setBriefState}
              />
            </div>

          </div>

          {/* Step 3 — YouTube publish, full width, only after successful render */}
          {renderResult?.success && (renderResult.preview_url || renderResult.url) && (
            <div className="pipeline-step-wrapper pipeline-step-wrapper--full mt-8">
              <div className="step-badge step-badge--yt">03</div>
              <div className="step-meta">
                <h2 className="step-title">Publish to YouTube</h2>
                <p className="step-subtitle">Review the rendered video and upload it to your channel.</p>
              </div>
              <YouTubePublishStep
                result={renderResult}
                apiBase={apiBase}
                onPublished={() => setRenderResult(null)}
              />
            </div>
          )}

        </div>
      </section>
    </div>
  );
}
