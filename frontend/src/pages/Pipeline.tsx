import { useRef, useState } from "react";
import { type PipelineResult } from "../components/VideoPipelinePanel";
import { ChatPanel } from "../components/ChatPanel";
import { ProcessVideoURLPayload } from "../types/pipeline";
import "./Pipeline.css";
import "./Pipeline.redesigned.css";

export default function Pipeline() {
  const [briefState, setBriefState] = useState<Record<string, unknown>>({});
  const [renderResult, setRenderResult] = useState<PipelineResult | null>(null);
  const [jobStatus, setJobStatus] = useState<PipelineResult | null>(null);

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
  };

  const startStatusPolling = async (projectId: string) => {
    stopStatusPolling();
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

        if (
          data.controller_status_category === "complete" ||
          data.controller_status_category === "failed" ||
          data.controller_status_category === "blocked" ||
          data.controller_status_category === "waiting_for_user_input"
        ) {
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

  const handleRenderResult = (result: PipelineResult | null) => {
    setRenderResult(result);

    if (!result) {
      setJobStatus(null);
      stopStatusPolling();
      return;
    }

    setJobStatus(result);

    if (
      result.project_id &&
      !(
        result.controller_status_category === "complete" ||
        result.controller_status_category === "failed" ||
        result.controller_status_category === "blocked" ||
        result.controller_status_category === "waiting_for_user_input"
      )
    ) {
      void startStatusPolling(result.project_id);
    } else {
      stopStatusPolling();
    }
  };

  const submitChatPipelinePayload = async (payload: ProcessVideoURLPayload) => {
    try {
      const response = await fetch(`${apiBase}/process-video-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data: PipelineResult = await response.json();
      handleRenderResult(data);

      return data;
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : "Network error while calling /process-video-url.";
      return { success: false, error: message };
    }
  };

  const displayResult = jobStatus || renderResult;

  displayResultRef.current = displayResult;

  return (
    <div className="min-h-screen pipeline-page pipeline-page-redesigned">
      <div className="container mx-auto px-6 max-w-5xl pb-16 pt-24">
        <ChatPanel
          apiBase={apiBase}
          analyzerOutput=""
          currentState={briefState}
          onStateUpdate={setBriefState}
          activeJobId={displayResult?.project_id || null}
          activeJobStatusCategory={displayResult?.controller_status_category || null}
          onPipelineResult={(result) => handleRenderResult(result as PipelineResult | null)}
          onSubmitPipelinePayload={submitChatPipelinePayload}
        />
      </div>
    </div>
  );
}
