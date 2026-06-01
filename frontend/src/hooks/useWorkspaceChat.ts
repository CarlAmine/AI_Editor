import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { buildPipelinePayloadFromChatState } from "../utils/chatPayload";
import {
  buildDefaultTextReplacements,
  normalizeReferenceAnalysis,
} from "../utils/referenceAnalysis";
import { fetchDriveStatus, fetchProviderHealth } from "../lib/api";
import { resolveChatSubmitTarget } from "../lib/chat";
import type { ProcessVideoURLPayload } from "../types/pipeline";

export type ChatMessage = {
  id: string;
  from: "user" | "assistant";
  text: string;
  timestamp: Date;
  streaming?: boolean;
};

type ChatTurnRequest = {
  user_input: string;
  current_state: Record<string, unknown>;
  analyzer_output: string;
};

type ChatTurnResponse = {
  updated_state?: Record<string, unknown>;
  next_message?: string;
  is_complete?: boolean;
  final_report?: string | null;
};

type UseWorkspaceChatOptions = {
  apiBase: string;
  externalState?: Record<string, unknown>;
  onStateUpdate?: (state: Record<string, unknown>) => void;
  activeJobId?: string | null;
  activeJobStatusCategory?: string | null;
  onPipelineResult?: (result: Record<string, unknown>) => void;
  onSubmitPipelinePayload?: (payload: ProcessVideoURLPayload) => Promise<unknown>;
};

export function normalizeSources(value: unknown): Array<{ url: string; label?: number }> {
  if (!Array.isArray(value)) return [];
  return value
    .map((item: unknown, idx) => {
      if (typeof item === "string") return { url: item, label: idx + 1 };
      if (item && typeof item === "object") {
        const row = item as { url?: string; label?: number };
        return { url: String(row.url || ""), label: row.label ?? idx + 1 };
      }
      return null;
    })
    .filter(Boolean) as Array<{ url: string; label?: number }>;
}

export function normalizeTextOverlays(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? (value as Array<Record<string, unknown>>) : [];
}

function createInitialSlotMapping(
  referenceSlots: Array<Record<string, unknown>>,
): Array<Record<string, unknown>> {
  return referenceSlots.map((slot, index) => {
    const slotId = Number(slot.slotId ?? slot.slot_id ?? index + 1);
    const duration = Number(slot.duration ?? Math.max(0, Number(slot.end ?? 0) - Number(slot.start ?? 0)));
    return {
      slot_id: slotId,
      clip_id: `slot_${slotId}`,
      clip_url: "",
      source_start: 0,
      source_end: Number.isFinite(duration) ? duration : 0,
    };
  });
}

function createTextOverlayRows(textMoments: Array<Record<string, unknown>>) {
  return textMoments.map((moment, index) => {
    const id = String(moment.id || moment.overlay_id || `text_${index + 1}`);
    const detectedText = String(moment.detectedText || moment.detected_text || "");
    return {
      id,
      overlay_id: id,
      start: Number(moment.start ?? 0),
      end: Number(moment.end ?? 0),
      detectedText,
      detected_text: detectedText,
      slotId: moment.slotId ?? moment.slot_id ?? null,
      slot_id: moment.slotId ?? moment.slot_id ?? null,
      action: "keep",
      render_text: detectedText,
      approximate_timing: Boolean(moment.approximateTiming ?? moment.approximate_timing),
    };
  });
}

export function useWorkspaceChat({
  apiBase,
  externalState = {},
  onStateUpdate,
  activeJobId = null,
  activeJobStatusCategory = null,
  onPipelineResult,
  onSubmitPipelinePayload,
}: UseWorkspaceChatOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [currentState, setCurrentState] = useState<Record<string, unknown>>(externalState);
  const [isLoading, setIsLoading] = useState(false);
  const [isPipelineSubmitting, setIsPipelineSubmitting] = useState(false);
  const [finalReport, setFinalReport] = useState<string | null>(null);
  const [showFieldsEditor, setShowFieldsEditor] = useState(false);
  const chatWindowRef = useRef<HTMLDivElement>(null);
  const completedStreamingMessagesRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    setCurrentState(externalState || {});
  }, [externalState]);

  useEffect(() => {
    if (chatWindowRef.current) {
      chatWindowRef.current.scrollTop = chatWindowRef.current.scrollHeight;
    }
  }, [
    messages,
    isLoading,
    currentState?.phase,
    currentState?.ready_to_submit,
    currentState?.slot_mapping,
    currentState?.reference_slots,
    showFieldsEditor,
  ]);

  const updateState = useCallback(
    (newState: Record<string, unknown>) => {
      setCurrentState(newState);
      onStateUpdate?.(newState);
    },
    [onStateUpdate],
  );

  const updateMessageCompletion = useCallback((messageId: string) => {
    completedStreamingMessagesRef.current.add(messageId);
    setMessages((prev) =>
      prev.map((message) =>
        message.id === messageId ? { ...message, streaming: false } : message,
      ),
    );
  }, []);

  const appendMessage = useCallback(
    (from: "user" | "assistant", text: string, options?: { streaming?: boolean }) => {
      const messageId = `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
      const streaming = options?.streaming ?? from === "assistant";
      setMessages((prev) => [
        ...prev,
        {
          id: messageId,
          from,
          text,
          timestamp: new Date(),
          streaming,
        },
      ]);
      if (streaming) {
        completedStreamingMessagesRef.current.delete(messageId);
      }
      return messageId;
    },
    [],
  );

  const triggerReferenceAnalysis = useCallback(
    async (referenceUrl: string, jobId?: string) => {
      setIsLoading(true);
      const streamingId = appendMessage(
        "assistant",
        "Analyzing the reference video and preparing the replacement forms.",
      );
      try {
        const response = await fetch(`${apiBase}/chat/analyze-reference`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reference_url: referenceUrl, job_id: jobId }),
        });
        const data = await response.json();
        if (!data.success) {
          throw new Error(data.error || "Analysis failed.");
        }

        const normalized = normalizeReferenceAnalysis(data);
        const slotMapping = createInitialSlotMapping(
          normalized.slots.map((slot) => ({
            slotId: slot.slotId,
            slot_id: slot.slotId,
            duration: slot.duration,
            start: slot.start,
            end: slot.end,
          })),
        );

        const nextState = {
          ...currentState,
          primary_url: referenceUrl,
          reference_analysis: normalized.summary,
          reference_summary: normalized.summary,
          reference_slots: normalized.slots.map((slot) => ({
            slot_id: slot.slotId,
            slotId: slot.slotId,
            role: slot.role,
            start_time: slot.start,
            end_time: slot.end,
            duration: slot.duration,
            description: slot.description || "",
          })),
          text_moments: normalized.textMoments.map((moment) => ({
            id: moment.id,
            overlay_id: moment.id,
            start: moment.start,
            end: moment.end,
            detectedText: moment.detectedText,
            detected_text: moment.detectedText,
            slotId: moment.slotId ?? null,
            slot_id: moment.slotId ?? null,
            approximateTiming: moment.approximateTiming ?? false,
          })),
          text_overlays: createTextOverlayRows(
            normalized.textMoments.map((moment) => ({
              id: moment.id,
              overlay_id: moment.id,
              start: moment.start,
              end: moment.end,
              detectedText: moment.detectedText,
              detected_text: moment.detectedText,
              slotId: moment.slotId ?? null,
              slot_id: moment.slotId ?? null,
              approximateTiming: moment.approximateTiming ?? false,
            })),
          ),
          text_replacements: buildDefaultTextReplacements(normalized.textMoments),
          slot_mapping: slotMapping,
          use_same_target_video_for_all_slots: false,
          shared_target_video_url: "",
          reference_job_id: data.job_id,
          reference_analysis_bundle: {
            summary: normalized.summary,
            slots: normalized.slots,
            text_moments: normalized.textMoments,
          },
          phase: normalized.textMoments.length > 0 ? "awaiting_slot_mapping" : "awaiting_slot_mapping",
        };

        updateState(nextState);
        appendMessage(
          "assistant",
          data.chat_message ||
            "Reference analysis is ready. Review the summary card and complete the replacement forms below.",
        );
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Unknown error";
        appendMessage(
          "assistant",
          `Reference analysis failed: ${message}. You can continue by editing the project fields.`,
        );
      } finally {
        updateMessageCompletion(streamingId);
        setIsLoading(false);
      }
    },
    [apiBase, appendMessage, currentState, updateMessageCompletion, updateState],
  );

  const handleConfirmAndRender = useCallback(async () => {
    if (!onSubmitPipelinePayload) {
      appendMessage("assistant", "Render submission is not available in this session.");
      return;
    }
    setIsPipelineSubmitting(true);
    appendMessage("assistant", "Submitting the edit plan and starting the render pipeline.");
    try {
      const payload = buildPipelinePayloadFromChatState(currentState);
      const result = (await onSubmitPipelinePayload(payload)) as {
        success?: boolean;
        error?: string;
      };
      if (result && result.success) {
        appendMessage(
          "assistant",
          "Render started. Track progress in the status panel, and check provider or Drive readiness anytime.",
        );
        updateState({ ...currentState, phase: "pipeline_running" });
      } else {
        throw new Error(result?.error || "Pipeline failed to start.");
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Unknown error";
      appendMessage("assistant", `Render failed: ${message}`);
    } finally {
      setIsPipelineSubmitting(false);
    }
  }, [appendMessage, currentState, onSubmitPipelinePayload, updateState]);

  const handleEditPlan = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${apiBase}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_input: "edit plan",
          current_state: currentState,
          analyzer_output: "",
        }),
      });
      const data = await response.json();
      if (data.updated_state) {
        updateState(data.updated_state);
      }
      if (data.next_message) {
        appendMessage("assistant", data.next_message);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Unknown error";
      appendMessage("assistant", `Failed to adjust plan: ${message}`);
    } finally {
      setIsLoading(false);
    }
  }, [apiBase, appendMessage, currentState, updateState]);

  const handleClearChat = useCallback(() => {
    setMessages([]);
    setInput("");
    setFinalReport(null);
    setShowFieldsEditor(false);
    completedStreamingMessagesRef.current.clear();
    updateState({});
  }, [updateState]);

  const maybeHandleLocalStatusRequest = useCallback(
    async (userText: string) => {
      const text = userText.trim();
      if (!text) return false;

      const wantsHealth =
        /\b(provider\s+health|health\s+providers|providers?\s+status|service\s+provider\s+health)\b/i.test(
          text,
        );
      const wantsDriveStatus =
        /\b(google\s+drive\s+status|drive\s+status|drive\s+connection|connect\s+drive)\b/i.test(
          text,
        );

      if (!wantsHealth && !wantsDriveStatus) return false;

      setIsLoading(true);
      try {
        if (wantsHealth) {
          const data = await fetchProviderHealth(apiBase);
          const providers = data?.providers || {};
          const readyCount = Object.values(providers).filter((p) => p?.ready).length;
          const totalCount = Object.keys(providers).length;
          const lines = [
            `Provider health: ${readyCount}/${totalCount} ready.`,
            ...Object.entries(providers).map(([name, p]) => {
              const status = p?.ready ? "ready" : p?.configured ? "not ready" : "not configured";
              const required = p?.required ? "required" : "optional";
              const msg = p?.message ? ` - ${p.message}` : "";
              return `- ${name}: ${status} (${required})${msg}`;
            }),
          ];
          appendMessage("assistant", lines.join("\n"));
        }

        if (wantsDriveStatus) {
          const data = await fetchDriveStatus(apiBase);
          if (data?.connected) {
            appendMessage("assistant", `Google Drive: connected${data?.email ? ` as ${data.email}` : ""}.`);
          } else {
            appendMessage(
              "assistant",
              `Google Drive: not connected${data?.error ? ` - ${data.error}` : ""}.`,
            );
          }
        }
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "unknown error";
        appendMessage("assistant", `Status request failed: ${message}`);
      } finally {
        setIsLoading(false);
      }
      return true;
    },
    [apiBase, appendMessage],
  );

  const handleSubmit = useCallback(
    async (e?: FormEvent) => {
      e?.preventDefault();
      if (!input.trim()) return;

      const userText = input.trim();
      appendMessage("user", userText, { streaming: false });
      setInput("");

      if (await maybeHandleLocalStatusRequest(userText)) {
        return;
      }

      setIsLoading(true);

      const payload: ChatTurnRequest = {
        user_input: userText,
        current_state: currentState,
        analyzer_output: "",
      };
      const target = resolveChatSubmitTarget(apiBase, activeJobStatusCategory, activeJobId);

      try {
        const response = await fetch(target.endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(target.isResume ? { message: userText } : payload),
        });

        const data: ChatTurnResponse & Record<string, unknown> = await response.json();

        if (target.isResume) {
          onPipelineResult?.(data);
        }

        if (data.updated_state) {
          updateState(data.updated_state);
          if (
            data.updated_state.phase === "reference_url_received" &&
            data.updated_state.primary_url
          ) {
            void triggerReferenceAnalysis(
              data.updated_state.primary_url as string,
              (data.updated_state.reference_job_id || undefined) as string | undefined,
            );
          }
        }

        if (data.next_message) {
          appendMessage("assistant", data.next_message);
        }

        if (data.is_complete && data.final_report) {
          setFinalReport(data.final_report);
        }
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Something went wrong while contacting the chat endpoint.";
        appendMessage("assistant", message);
      } finally {
        setIsLoading(false);
      }
    },
    [
      activeJobId,
      activeJobStatusCategory,
      apiBase,
      appendMessage,
      currentState,
      input,
      maybeHandleLocalStatusRequest,
      onPipelineResult,
      triggerReferenceAnalysis,
      updateState,
    ],
  );

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (!isLoading && input.trim()) {
          void handleSubmit();
        }
      }
    },
    [handleSubmit, input, isLoading],
  );

  const phase = String(currentState?.phase || "");
  const shouldShowFinalPlan =
    phase === "awaiting_final_confirmation" || currentState?.ready_to_submit === true;

  return {
    messages,
    input,
    setInput,
    currentState,
    updateState,
    isLoading,
    isPipelineSubmitting,
    finalReport,
    showFieldsEditor,
    setShowFieldsEditor,
    chatWindowRef,
    handleSubmit,
    handleKeyDown,
    handleClearChat,
    handleConfirmAndRender,
    handleEditPlan,
    shouldShowFinalPlan,
    normalizeSources,
    normalizeTextOverlays,
    updateMessageCompletion,
    completedStreamingMessagesRef,
  };
}
