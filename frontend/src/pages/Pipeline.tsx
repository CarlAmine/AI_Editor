import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";

import {
  VideoPipelinePanel,
  type AssistantFeedback,
  type PipelineResult,
} from "../components/VideoPipelinePanel";
import { ChatPanel } from "../components/ChatPanel";
import { HeroHeader } from "../components/HeroHeader";
import { ProviderCard } from "../components/ProviderCard";
import { ResultPreviewCard } from "../components/ResultPreviewCard";
import { StatusRail } from "../components/StatusRail";
import { YouTubePublishStep } from "../components/YouTubePublishStep";
import "./Pipeline.css";
import "./Pipeline.redesigned.css";

type AssistantEvent = {
  id: number;
  message: string;
  statePatch?: Record<string, unknown>;
};

type ProviderHealthEntry = {
  name?: string;
  required?: boolean;
  configured?: boolean;
  ready?: boolean;
  code?: string;
  message?: string;
};

type ProviderHealthPayload = {
  success?: boolean;
  ready?: boolean;
  providers?: Record<string, ProviderHealthEntry>;
};

type DriveStatus = {
  connected: boolean;
  email?: string | null;
  error?: string;
};

const isTerminalCategory = (category?: string) =>
  category === "complete" ||
  category === "failed" ||
  category === "blocked" ||
  category === "waiting_for_user_input";

export default function Pipeline() {
  const [briefState, setBriefState] = useState<Record<string, unknown>>({});
  const [renderResult, setRenderResult] = useState<PipelineResult | null>(null);
  const [assistantEvent, setAssistantEvent] = useState<AssistantEvent | null>(null);
  const [jobStatus, setJobStatus] = useState<PipelineResult | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const [providerHealth, setProviderHealth] = useState<ProviderHealthPayload | null>(
    null
  );
  const [isHealthLoading, setIsHealthLoading] = useState(false);
  const [driveStatus, setDriveStatus] = useState<DriveStatus | null>(null);
  const [driveMessage, setDriveMessage] = useState<string | null>(null);
  const [isDriveLoading, setIsDriveLoading] = useState(false);

  const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const displayResultRef = useRef<PipelineResult | null>(null);

  const apiBase = (import.meta.env.VITE_API_BASE_URL || window.location.origin).replace(
    /\/$/,
    ""
  );

  const stopStatusPolling = () => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
    setIsPolling(false);
  };

  const fetchProviderHealth = async () => {
    setIsHealthLoading(true);
    try {
      const response = await fetch(`${apiBase}/health/providers`);
      if (!response.ok) {
        throw new Error(`Provider health request failed with ${response.status}`);
      }
      const data: ProviderHealthPayload = await response.json();
      setProviderHealth(data);
    } catch (err: unknown) {
      setProviderHealth({
        success: false,
        ready: false,
        providers: {},
      });
      console.error("Provider health check failed:", err);
    } finally {
      setIsHealthLoading(false);
    }
  };

  const fetchDriveStatus = async () => {
    setIsDriveLoading(true);
    try {
      const response = await fetch(`${apiBase}/google-drive/oauth/status`);
      const data: DriveStatus = await response.json();
      setDriveStatus(data);
      setDriveMessage(
        data.connected
          ? "Google Drive connected successfully."
          : data.error || "Google Drive is not connected yet."
      );
      return data;
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : "Unable to check Google Drive connection.";
      setDriveStatus({ connected: false, error: message });
      setDriveMessage(message);
      return { connected: false, error: message };
    } finally {
      setIsDriveLoading(false);
    }
  };

  const handleConnectDrive = async () => {
    setIsDriveLoading(true);
    setDriveMessage(null);
    try {
      const response = await fetch(`${apiBase}/google-drive/oauth/start`, {
        method: "GET",
      });
      const data = await response.json();
      if (!response.ok || data.success === false) {
        throw new Error(data.error || "Failed to start Google Drive OAuth.");
      }
      if (!data.auth_url) {
        throw new Error("No Google OAuth URL was returned by backend.");
      }
      const popup = window.open(data.auth_url, "_blank", "width=520,height=720");
      if (!popup) {
        throw new Error("Popup blocked. Please allow popups and try again.");
      }
      setDriveMessage("Google sign-in opened. Finish login and the status will refresh.");

      for (let i = 0; i < 45; i += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 2000));
        const status = await fetchDriveStatus();
        if (status.connected) {
          return;
        }
      }
      setDriveMessage("Login not completed yet. Use Check Status to verify later.");
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Error starting Google Drive OAuth.";
      setDriveStatus({ connected: false, error: message });
      setDriveMessage(message);
    } finally {
      setIsDriveLoading(false);
    }
  };

  const startStatusPolling = async (projectId: string) => {
    stopStatusPolling();
    setIsPolling(true);
    let pollCount = 0;
    const maxPolls = 300;

    const poll = async () => {
      try {
        const response = await fetch(`${apiBase}/jobs/${projectId}/status`);
        if (!response.ok) {
          throw new Error(`Status polling failed with ${response.status}`);
        }

        const data: PipelineResult = await response.json();
        const currentDisplay = displayResultRef.current;

        if (
          currentDisplay?.success &&
          currentDisplay.controller_status_category === "complete" &&
          data.controller_status_category !== "complete"
        ) {
          return;
        }

        setJobStatus(data);

        if (isTerminalCategory(data.controller_status_category)) {
          stopStatusPolling();
          return;
        }

        pollCount += 1;
        if (pollCount >= maxPolls) {
          stopStatusPolling();
        }
      } catch (err) {
        console.error("Error polling job status:", err);
      }
    };

    pollingIntervalRef.current = setInterval(poll, 2000);
    await poll();
  };

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

  const handleRenderResult = (result: PipelineResult | null) => {
    setRenderResult(result);

    if (!result) {
      setJobStatus(null);
      stopStatusPolling();
      return;
    }

    setJobStatus(result);

    if (result.project_id && !isTerminalCategory(result.controller_status_category)) {
      void startStatusPolling(result.project_id);
    } else {
      stopStatusPolling();
    }
  };

  const displayResult = jobStatus || renderResult;

  useEffect(() => {
    displayResultRef.current = displayResult;
  }, [displayResult]);

  useEffect(() => {
    void fetchProviderHealth();
    void fetchDriveStatus();

    return () => {
      stopStatusPolling();
    };
  }, []);

  const readyProviders = Object.values(providerHealth?.providers || {}).filter(
    (entry) => entry.ready
  ).length;
  const totalProviders = Object.keys(providerHealth?.providers || {}).length;
  const providerMessage =
    totalProviders > 0
      ? `${readyProviders}/${totalProviders} providers ready`
      : "Check model, render, and storage readiness.";

  return (
    <div className="min-h-screen pipeline-page pipeline-page-redesigned">
      <HeroHeader />

      <div className="container mx-auto px-6 max-w-7xl pb-16">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <motion.div
            className="lg:col-span-2 space-y-6"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.15 }}
          >
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
                activeJobId={displayResult?.project_id || null}
                activeJobStatusCategory={displayResult?.controller_status_category || null}
                onPipelineResult={(result) =>
                  handleRenderResult(result as PipelineResult | null)
                }
              />
            </div>
          </motion.div>

          <motion.div
            className="space-y-6"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.6, delay: 0.25 }}
          >
            <StatusRail result={displayResult} isPolling={isPolling} />

            <ProviderCard
              provider="health"
              status={
                isHealthLoading
                  ? "connecting"
                  : providerHealth
                    ? providerHealth.ready
                      ? "connected"
                      : "error"
                    : "disconnected"
              }
              message={providerMessage}
              onCheckStatus={() => void fetchProviderHealth()}
              isLoading={isHealthLoading}
            />

            <ProviderCard
              provider="google-drive"
              status={
                isDriveLoading
                  ? "connecting"
                  : driveStatus?.connected
                    ? "connected"
                    : driveStatus?.error
                      ? "error"
                      : "disconnected"
              }
              email={driveStatus?.email || null}
              message={driveMessage}
              onConnect={() => void handleConnectDrive()}
              onCheckStatus={() => void fetchDriveStatus()}
              isLoading={isDriveLoading}
            />

            {displayResult?.success && (displayResult.preview_url || displayResult.url) && (
              <ResultPreviewCard result={displayResult} apiBase={apiBase} />
            )}
          </motion.div>
        </div>

        {displayResult?.success && (displayResult.preview_url || displayResult.url) && (
          <motion.div
            className="pipeline-step-wrapper pipeline-step-wrapper--full mt-12"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.35 }}
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
                stopStatusPolling();
              }}
            />
          </motion.div>
        )}
      </div>
    </div>
  );
}
