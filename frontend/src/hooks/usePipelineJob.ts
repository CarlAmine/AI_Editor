import { useCallback, useEffect, useRef, useState } from "react";
import type { PipelineResult } from "../components/VideoPipelinePanel";
import type { ProcessVideoURLPayload } from "../types/pipeline";
import {
  fetchJobStatus,
  getApiBase,
  isTerminalJobCategory,
  submitPipelinePayload,
} from "../lib/api";

export function usePipelineJob() {
  const apiBase = getApiBase();
  const [briefState, setBriefState] = useState<Record<string, unknown>>({});
  const [renderResult, setRenderResult] = useState<PipelineResult | null>(null);
  const [jobStatus, setJobStatus] = useState<PipelineResult | null>(null);
  const [isPolling, setIsPolling] = useState(false);

  const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const displayResultRef = useRef<PipelineResult | null>(null);

  const displayResult = jobStatus || renderResult;
  displayResultRef.current = displayResult;

  const stopStatusPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
    setIsPolling(false);
  }, []);

  const startStatusPolling = useCallback(
    async (projectId: string) => {
      stopStatusPolling();
      setIsPolling(true);
      let pollCount = 0;
      const maxPolls = 300;

      const poll = async () => {
        try {
          const data = await fetchJobStatus(apiBase, projectId);
          const currentDisplay = displayResultRef.current;

          if (
            currentDisplay?.success &&
            currentDisplay.controller_status_category === "complete" &&
            data.controller_status_category !== "complete"
          ) {
            return;
          }

          setJobStatus(data);

          if (isTerminalJobCategory(data.controller_status_category)) {
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
    },
    [apiBase, stopStatusPolling]
  );

  const handleRenderResult = useCallback(
    (result: PipelineResult | null) => {
      setRenderResult(result);

      if (!result) {
        setJobStatus(null);
        stopStatusPolling();
        return;
      }

      setJobStatus(result);

      if (result.project_id && !isTerminalJobCategory(result.controller_status_category)) {
        void startStatusPolling(result.project_id);
      } else {
        stopStatusPolling();
      }
    },
    [startStatusPolling, stopStatusPolling]
  );

  const submitChatPipelinePayload = useCallback(
    async (payload: ProcessVideoURLPayload) => {
      try {
        const data = await submitPipelinePayload(apiBase, payload);
        handleRenderResult(data);
        return data;
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Network error while calling /process-video-url.";
        return { success: false, error: message } as PipelineResult;
      }
    },
    [apiBase, handleRenderResult]
  );

  useEffect(() => {
    return () => stopStatusPolling();
  }, [stopStatusPolling]);

  return {
    apiBase,
    briefState,
    setBriefState,
    displayResult,
    isPolling,
    handleRenderResult,
    submitChatPipelinePayload,
    stopStatusPolling,
  };
}
