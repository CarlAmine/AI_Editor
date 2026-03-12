/* ============================================================
   Pipeline Page — Functional Pipeline UI
   Uses VideoPipelinePanel + ChatPanel
   ============================================================ */

import { useState } from "react";
import { VideoPipelinePanel } from "../components/VideoPipelinePanel";
import { ChatPanel } from "../components/ChatPanel";
import "./Pipeline.css";

export default function Pipeline() {
  const [briefState, setBriefState] = useState<Record<string, unknown>>({});
  const apiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:10000";

  return (
    <div className="min-h-screen pt-24 pipeline-page">
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

      <section className="pb-16">
        <div className="container mx-auto px-6 max-w-7xl">
          <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] gap-6">
            <VideoPipelinePanel apiBase={apiBase} currentState={briefState} />
            <ChatPanel apiBase={apiBase} analyzerOutput="" onStateUpdate={setBriefState} />
          </div>
        </div>
      </section>
    </div>
  );
}

