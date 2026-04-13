import { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import {
  VideoPipelinePanel,
  type AssistantFeedback,
  type PipelineResult,
} from "../components/VideoPipelinePanel";
import { ChatPanel } from "../components/ChatPanel";
import { YouTubePublishStep } from "../components/YouTubePublishStep";
import { HeroHeader } from "../components/HeroHeader";
import { StatusRail } from "../components/StatusRail";
import { ResultPreviewCard } from "../components/ResultPreviewCard";
import "./Pipeline.css";

type AssistantEvent = {
  id: number;
  message: string;
  statePatch?: Record<string, unknown>;
};

export default function Pipeline() {
  const [briefState, setBriefState] = useState<Record<string, unknown>>({});
  const [renderResult, setRenderResult] = useState<PipelineResult | null>(null);
  const [assistantEvent, setAssistantEvent] = useState<AssistantEvent | null>(null);
  const [jobStatus, setJobStatus] = useState<PipelineResult | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  
  const apiBase = (import.meta.env.VITE_API_BASE_URL || window.location.origin).replace(
    /\/$/,
    ""
  );

  const handleAssistantFeedback = (feedback: AssistantFeedback) => {
    const statePatch = feedback.state_patch || {};
    if (Object.keys(statePatch).length > 0) {
      setBriefState((prev) => ({
        ...prev,
        ...statePatch,
      }));
    }
    if (feedback.route_to_chat && feedback.message) {
      setAssistantEvent({
        id: Date.now(),
        message: feedback.message,
        statePatch,
      });
    }
  };

  const startStatusPolling = async (projectId: string) => {
    setIsPolling(true);
    let pollCount = 0;
    const maxPolls = 300; // ~10 minutes with 2s interval

    const poll = async () => {
      try {
        const response = await fetch(`${apiBase}/jobs/${projectId}/status`);
        if (!response.ok) {
          console.error("Status polling failed:", response.statusText);
          return;
        }

        const data: PipelineResult = await response.json();
        
        // Never overwrite a successful final result with a worse stale response
        if (renderResult?.success && data.controller_status_category !== "complete") {
          return;
        }

        setJobStatus(data);

        // Check for terminal states
        if (
          data.controller_status_category === "complete" ||
          data.controller_status_category === "failed" ||
          data.controller_status_category === "blocked"
        ) {
          stopStatusPolling();
          return;
        }

        pollCount++;
        if (pollCount >= maxPolls) {
          stopStatusPolling();
        }
      } catch (err) {
        console.error("Error polling job status:", err);
      }
    };

    pollingIntervalRef.current = setInterval(poll, 2000);
    // Immediate first poll
    await poll();
  };

  const stopStatusPolling = () => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
    setIsPolling(false);
  };

  const handleRenderResult = (result: PipelineResult | null) => {
    setRenderResult(result);
    
    if (result?.project_id && !jobStatus) {
      startStatusPolling(result.project_id);
    }
  };

  useEffect(() => {
    return () => {
      stopStatusPolling();
    };
  }, []);

  // Merge job status into render result for display
  const displayResult = jobStatus || renderResult;

  return (
    <div className="min-h-screen pipeline-page-redesigned">
      {/* Animated Hero Header */}
      <HeroHeader />

      {/* Main Content Container */}
      <div className="container mx-auto px-6 max-w-7xl py-12">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column: Input Orchestration + Chat */}
          <motion.div
            className="lg:col-span-2 space-y-6"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
          >
            {/* Step 1: Build Your Edit */}
            <div className="pipeline-step-wrapper">
              <div className="step-badge">01</div>
              <div className="step-meta">
                <h2 className="step-title">Build Your Edit</h2>
                <p className="step-subtitle">
                  Configure sources, brief, and render settings.
                </p>
              </div>
              <VideoPipelinePanel
                apiBase={apiBase}
                currentState={briefState}
                onAnalyzerSummary={() => {}}
                onAssistantFeedback={handleAssistantFeedback}
                onResult={handleRenderResult}
              />
            </div>

            {/* Step 2: Brief the Assistant */}
            <div className="pipeline-step-wrapper">
              <div className="step-badge">02</div>
              <div className="step-meta">
                <h2 className="step-title">Brief the Assistant</h2>
                <p className="step-subtitle">
                  Refine your creative brief through conversation.
                </p>
              </div>
              <ChatPanel
                apiBase={apiBase}
                analyzerOutput=""
                currentState={briefState}
                onStateUpdate={setBriefState}
                assistantEvent={assistantEvent}
              />
            </div>
          </motion.div>

          {/* Right Column: Status Rail + Preview */}
          <motion.div
            className="space-y-6"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
          >
            {/* Status Rail */}
            <StatusRail
              result={displayResult}
              isPolling={isPolling}
              apiBase={apiBase}
            />

            {/* Result Preview Card */}
            {displayResult?.success && (displayResult.preview_url || displayResult.url) && (
              <ResultPreviewCard
                result={displayResult}
                apiBase={apiBase}
              />
            )}
          </motion.div>
        </div>

        {/* Full Width: Publish to YouTube */}
        {displayResult?.success && (displayResult.preview_url || displayResult.url) && (
          <motion.div
            className="pipeline-step-wrapper pipeline-step-wrapper--full mt-12"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
          >
            <div className="step-badge step-badge--yt">03</div>
            <div className="step-meta">
              <h2 className="step-title">Publish to YouTube</h2>
              <p className="step-subtitle">
                Review the rendered video and upload it to your channel.
              </p>
            </div>
            <YouTubePublishStep
              result={displayResult}
              apiBase={apiBase}
              onPublished={() => {
                setRenderResult(null);
                setJobStatus(null);
              }}
            />
          </motion.div>
        )}
      </div>
    </div>
  );
}
