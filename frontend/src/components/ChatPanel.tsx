import React, {
  useState,
  FormEvent,
  useEffect,
  useRef,
  KeyboardEvent,
} from "react";
import { AnimatePresence, motion } from "framer-motion";
import { RotateCcw, Send, Sparkles } from "lucide-react";
import { ProcessVideoURLPayload } from "../types/pipeline";
import { ReferenceSummaryCard } from "./ReferenceSummaryCard";
import { FinalPlanCard } from "./FinalPlanCard";
import { buildPipelinePayloadFromChatState } from "../utils/chatPayload";
import { resolveChatSubmitTarget } from "../lib/chat";

export { resolveChatSubmitTarget };

type Props = {
  apiBase: string;
  analyzerOutput: string;
  currentState?: Record<string, unknown>;
  onStateUpdate?: (state: Record<string, unknown>) => void;
  assistantEvent?: AssistantEvent | null;
  activeJobId?: string | null;
  activeJobStatusCategory?: string | null;
  onPipelineResult?: (result: Record<string, unknown>) => void;
  onSubmitPipelinePayload?: (payload: ProcessVideoURLPayload) => Promise<any>;
};

type AssistantEvent = {
  id: number;
  message: string;
  statePatch?: Record<string, unknown>;
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

type Message = {
  id: number;
  from: "user" | "assistant";
  text: string;
  timestamp: Date;
};

function normalizeSources(value: unknown): Array<{ url: string; label?: number }> {
  if (!Array.isArray(value)) return [];
  return value
    .map((item: any, idx) => {
      if (typeof item === "string") return { url: item, label: idx + 1 };
      if (item && typeof item === "object") {
        return { url: String(item.url || ""), label: item.label ?? idx + 1 };
      }
      return null;
    })
    .filter(Boolean) as Array<{ url: string; label?: number }>;
}

function normalizeTextOverlays(value: unknown): Array<Record<string, any>> {
  return Array.isArray(value) ? (value as Array<Record<string, any>>) : [];
}

export const ChatPanel: React.FC<Props> = ({
  apiBase,
  analyzerOutput,
  currentState: externalState = {},
  onStateUpdate,
  assistantEvent = null,
  activeJobId = null,
  activeJobStatusCategory = null,
  onPipelineResult,
  onSubmitPipelinePayload,
}) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [currentState, setCurrentState] =
    useState<Record<string, unknown>>(externalState);
  const [isLoading, setIsLoading] = useState(false);
  const [isPipelineSubmitting, setIsPipelineSubmitting] = useState(false);
  const [finalReport, setFinalReport] = useState<string | null>(null);
  const [showFieldsEditor, setShowFieldsEditor] = useState(false);
  const lastAssistantEventId = useRef<number | null>(null);
  const chatWindowRef = useRef<HTMLDivElement>(null);

  const triggerReferenceAnalysis = async (referenceUrl: string, jobId?: string) => {
    appendMessage("assistant", "Starting style-replication analysis on your reference video. This will take a few moments...");
    setIsLoading(true);
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

      const updatedState = {
        ...currentState,
        primary_url: referenceUrl,
        reference_analysis: data.summary,
        reference_slots: data.slots,
        text_overlays: data.text_overlays || [],
        text_overlays_resolved: !(data.text_overlays && data.text_overlays.length),
        reference_style_summary: data.summary.style_summary,
        reference_job_id: data.job_id,
        phase: "awaiting_sources"
      };
      updateState(updatedState);
      appendMessage("assistant", data.chat_message);
    } catch (err: any) {
      appendMessage("assistant", `Analysis failed: ${err.message}. You can still continue by filling fields below.`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleConfirmAndRender = async () => {
    if (!onSubmitPipelinePayload) {
      appendMessage("assistant", "Render submissions are not supported in this view.");
      return;
    }
    setIsPipelineSubmitting(true);
    appendMessage("assistant", "Submitting the plan and starting the rendering pipeline...");
    try {
      const payload = buildPipelinePayloadFromChatState(currentState);
      const result = await onSubmitPipelinePayload(payload);
      if (result && result.success) {
        appendMessage("assistant", "Render started successfully. If you need status or provider/Drive info, ask me in chat.");
        updateState({
          ...currentState,
          phase: "pipeline_running"
        });
      } else {
        throw new Error(result?.error || "Pipeline failed to start.");
      }
    } catch (err: any) {
      appendMessage("assistant", `Render failed: ${err.message}`);
    } finally {
      setIsPipelineSubmitting(false);
    }
  };

  const handleEditPlan = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${apiBase}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_input: "edit plan",
          current_state: currentState,
          analyzer_output: ""
        })
      });
      const data = await response.json();
      if (data.updated_state) {
        updateState(data.updated_state);
      }
      if (data.next_message) {
        appendMessage("assistant", data.next_message);
      }
    } catch (err: any) {
      appendMessage("assistant", `Failed to adjust plan: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

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
  ]);

  const updateState = (newState: Record<string, unknown>) => {
    setCurrentState(newState);
    onStateUpdate?.(newState);
  };

  const applyStatePatch = (patch: Record<string, unknown>) => {
    setCurrentState((prev) => {
      const merged = {
        ...prev,
        ...patch,
      };
      onStateUpdate?.(merged);
      return merged;
    });
  };

  const appendMessage = (from: "user" | "assistant", text: string) => {
    setMessages((prev) => [
      ...prev,
      { id: Date.now() + Math.random(), from, text, timestamp: new Date() },
    ]);
  };

  useEffect(() => {
    if (!assistantEvent || !assistantEvent.message) {
      return;
    }
    if (lastAssistantEventId.current === assistantEvent.id) {
      return;
    }
    lastAssistantEventId.current = assistantEvent.id;
    if (
      assistantEvent.statePatch &&
      Object.keys(assistantEvent.statePatch).length > 0
    ) {
      applyStatePatch(assistantEvent.statePatch);
    }
    appendMessage("assistant", assistantEvent.message);
  }, [assistantEvent]);

  const handleClearChat = () => {
    setMessages([]);
    setInput("");
    setFinalReport(null);
    setShowFieldsEditor(false);
    updateState({});
  };

  const maybeHandleLocalStatusRequest = async (userText: string) => {
    const text = userText.trim();
    if (!text) return false;

    const wantsHealth =
      /\b(provider\s+health|health\s+providers|providers?\s+status|service\s+provider\s+health)\b/i.test(
        text
      );
    const wantsDriveStatus =
      /\b(google\s+drive\s+status|drive\s+status|drive\s+connection)\b/i.test(text);

    if (!wantsHealth && !wantsDriveStatus) return false;

    setIsLoading(true);
    try {
      if (wantsHealth) {
        const response = await fetch(`${apiBase}/health/providers`);
        if (!response.ok) throw new Error(`Provider health request failed with ${response.status}`);
        const data = await response.json();
        const providers = (data?.providers || {}) as Record<string, any>;
        const readyCount = Object.values(providers).filter((p: any) => p?.ready).length;
        const totalCount = Object.keys(providers).length;
        const lines = [
          `Provider health: ${readyCount}/${totalCount} ready.`,
          ...Object.entries(providers).map(([name, p]) => {
            const status = p?.ready ? "ready" : p?.configured ? "not ready" : "not configured";
            const required = p?.required ? "required" : "optional";
            const msg = p?.message ? ` — ${p.message}` : "";
            return `- ${name}: ${status} (${required})${msg}`;
          }),
        ];
        appendMessage("assistant", lines.join("\n"));
      }

      if (wantsDriveStatus) {
        const response = await fetch(`${apiBase}/google-drive/oauth/status`);
        const data = await response.json();
        if (data?.connected) {
          appendMessage(
            "assistant",
            `Google Drive: connected${data?.email ? ` as ${data.email}` : ""}.`
          );
        } else {
          appendMessage(
            "assistant",
            `Google Drive: not connected${data?.error ? ` — ${data.error}` : ""}.`
          );
        }
      }
    } catch (err: any) {
      appendMessage("assistant", `Status request failed: ${err?.message || "unknown error"}`);
    } finally {
      setIsLoading(false);
    }
    return true;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userText = input.trim();
    appendMessage("user", userText);
    setInput("");
    if (await maybeHandleLocalStatusRequest(userText)) {
      return;
    }
    setIsLoading(true);

    const payload: ChatTurnRequest = {
      user_input: userText,
      current_state: currentState,
      analyzer_output: analyzerOutput || "",
    };
    const target = resolveChatSubmitTarget(
      apiBase,
      activeJobStatusCategory,
      activeJobId
    );

    try {
      const response = await fetch(target.endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          target.isResume ? { message: userText } : payload
        ),
      });

      const data: ChatTurnResponse & Record<string, unknown> =
        await response.json();

      if (target.isResume) {
        onPipelineResult?.(data);
      }

      if (data.updated_state) {
        updateState(data.updated_state);
        if (data.updated_state.phase === "reference_url_received" && data.updated_state.primary_url) {
          triggerReferenceAnalysis(data.updated_state.primary_url as string, (data.updated_state.reference_job_id || undefined) as string);
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
        err instanceof Error
          ? err.message
          : "Something went wrong while contacting the chat endpoint.";
      appendMessage("assistant", message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading && input.trim()) {
        handleSubmit(e as unknown as FormEvent);
      }
    }
  };

  const phase = String(currentState?.phase || "");
  const shouldShowFinalPlan =
    phase === "awaiting_final_confirmation" ||
    currentState?.ready_to_submit === true;

  const chatState = currentState as any;

  return (
    <section className="panel">
      <header className="panel-header">
        <div className="flex items-center gap-2">
          <Sparkles size={18} className="text-amber-400" />
          <h2 className="panel-title">Brief the Assistant</h2>
        </div>
        <p className="panel-caption">
          Refine the creative brief through conversation. The assistant tracks
          requirements and produces a final written brief.
        </p>
      </header>

      <div className="chat-window" ref={chatWindowRef}>
        <AnimatePresence>
          {messages.length === 0 && (
            <motion.div
              className="chat-empty"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
            >
              <div className="flex items-center justify-center mb-4">
                <div className="w-12 h-12 rounded-full bg-blue-500/10 border border-blue-500/30 flex items-center justify-center">
                  <Sparkles size={20} className="text-blue-400" />
                </div>
              </div>
              <p className="text-center mb-4">
                Hi! Send me the reference video whose editing style you want to replicate, for example:
              </p>
              <ul className="space-y-2">
                <li className="text-sm text-gray-400">
                  &ldquo;https://www.youtube.com/watch?v=dQw4w9WgXcQ&rdquo;
                </li>
                <li className="text-sm text-gray-400">
                  &ldquo;Replicate the editing rhythm of this TikTok: https://www.tiktok.com/@user/video/...&rdquo;
                </li>
              </ul>
            </motion.div>
          )}
        </AnimatePresence>

        <AnimatePresence mode="popLayout">
          {messages.map((message, idx) => (
            <motion.div
              key={message.id}
              className={
                message.from === "user"
                  ? "chat-bubble chat-bubble-user"
                  : "chat-bubble chat-bubble-assistant"
              }
              initial={{ opacity: 0, y: 10, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -10, scale: 0.96 }}
              transition={{ duration: 0.25, delay: idx * 0.04 }}
            >
              <span className="chat-author">
                {message.from === "user" ? "You" : "Assistant"}
              </span>
              <p className="chat-text">{message.text}</p>
              <span className="text-xs text-gray-600 mt-1">
                {message.timestamp.toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            </motion.div>
          ))}
        </AnimatePresence>

        <AnimatePresence>
          {isLoading && (
            <motion.div
              className="chat-bubble chat-bubble-assistant"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
            >
              <span className="chat-author">Assistant</span>
              <div className="typing-indicator">
                <motion.span
                  className="typing-dot"
                  animate={{ y: [0, -8, 0] }}
                  transition={{ duration: 0.6, repeat: Infinity, delay: 0 }}
                />
                <motion.span
                  className="typing-dot"
                  animate={{ y: [0, -8, 0] }}
                  transition={{ duration: 0.6, repeat: Infinity, delay: 0.2 }}
                />
                <motion.span
                  className="typing-dot"
                  animate={{ y: [0, -8, 0] }}
                  transition={{ duration: 0.6, repeat: Infinity, delay: 0.4 }}
                />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        {chatState.reference_analysis && chatState.reference_slots && (
          <ReferenceSummaryCard
            summary={chatState.reference_analysis as any}
            slots={chatState.reference_slots as any}
          />
        )}

        {shouldShowFinalPlan && (
          <FinalPlanCard
            state={currentState}
            onConfirm={handleConfirmAndRender}
            onEdit={handleEditPlan}
            isSubmitting={isPipelineSubmitting}
          />
        )}
      </div>

      <form className="chat-input-row" onSubmit={handleSubmit}>
        <textarea
          className="field-input chat-input"
          placeholder="Type your next message... (Enter to send, Shift+Enter for new line)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
        />
        <motion.button
          className="btn btn-primary chat-send"
          disabled={isLoading}
          type="submit"
          whileHover={{ scale: 1.04 }}
          whileTap={{ scale: 0.96 }}
        >
          <Send size={16} />
        </motion.button>
      </form>

      <div className="chat-meta">
        <motion.button
          type="button"
          className="btn btn-ghost"
          onClick={handleClearChat}
          disabled={isLoading}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
        >
          <RotateCcw size={14} />
          Clear Chat
        </motion.button>
        <motion.button
          type="button"
          className="btn btn-pill"
          onClick={() => setShowFieldsEditor((v) => !v)}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
        >
          {showFieldsEditor ? "Hide PKAB Fields" : "Edit PKAB Fields"}
        </motion.button>
        <AnimatePresence>
          {showFieldsEditor && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.25 }}
            >
              <div className="state-preview" style={{ padding: 12 }}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 10 }}>
                  <div className="field">
                    <label className="field-label">Reference (YouTube/TikTok) URL</label>
                    <input
                      className="field-input"
                      value={String((currentState as any)?.primary_url || "")}
                      onChange={(e) =>
                        updateState({
                          ...(currentState as any),
                          primary_url: e.target.value,
                        })
                      }
                      placeholder="https://www.youtube.com/watch?v=..."
                    />
                  </div>

                  <div className="field">
                    <label className="field-label">Google Drive folder link (optional)</label>
                    <input
                      className="field-input"
                      value={String((currentState as any)?.google_drive_link || "")}
                      onChange={(e) =>
                        updateState({
                          ...(currentState as any),
                          google_drive_link: e.target.value,
                        })
                      }
                      placeholder="https://drive.google.com/drive/folders/..."
                    />
                  </div>

                  <div className="field">
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: 10,
                      }}
                    >
                      <label className="field-label" style={{ margin: 0 }}>
                        Replacement clip URLs
                      </label>
                      <button
                        type="button"
                        className="btn btn-mini"
                        onClick={() => {
                          const next = normalizeSources((currentState as any)?.sources);
                          next.push({ url: "", label: next.length + 1 });
                          updateState({ ...(currentState as any), sources: next });
                        }}
                      >
                        Add URL
                      </button>
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      {normalizeSources((currentState as any)?.sources).length === 0 && (
                        <div style={{ fontSize: "0.8rem", color: "#94a3b8" }}>
                          Add your replacement YouTube/MP4 URLs here (one per slot).
                        </div>
                      )}
                      {normalizeSources((currentState as any)?.sources).map((src, idx) => (
                        <div key={idx} style={{ display: "flex", gap: 8 }}>
                          <input
                            className="field-input"
                            value={src.url}
                            onChange={(e) => {
                              const next = normalizeSources((currentState as any)?.sources);
                              next[idx] = { ...next[idx], url: e.target.value, label: idx + 1 };
                              updateState({ ...(currentState as any), sources: next });
                            }}
                            placeholder={`Clip URL #${idx + 1}`}
                          />
                          <button
                            type="button"
                            className="btn btn-mini btn-danger"
                            onClick={() => {
                              const next = normalizeSources((currentState as any)?.sources).filter(
                                (_, i) => i !== idx
                              );
                              updateState({ ...(currentState as any), sources: next });
                            }}
                          >
                            Remove
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="field">
                    <label className="field-label">Overlay texts (per detected sequence)</label>
                    {normalizeTextOverlays((currentState as any)?.text_overlays).length === 0 ? (
                      <div style={{ fontSize: "0.8rem", color: "#94a3b8" }}>
                        No overlays detected yet. Once the reference is analyzed, overlays (if found)
                        will appear here.
                      </div>
                    ) : (
                      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                        {normalizeTextOverlays((currentState as any)?.text_overlays).map(
                          (ov: any, idx: number) => (
                            <div
                              key={ov.overlay_id || `${idx}-${ov.start}-${ov.end}`}
                              style={{
                                border: "1px solid rgba(55, 65, 81, 0.7)",
                                borderRadius: 10,
                                padding: 10,
                                background: "rgba(2, 6, 23, 0.35)",
                              }}
                            >
                              <div style={{ fontSize: "0.78rem", color: "#94a3b8", marginBottom: 8 }}>
                                {Number(ov.start ?? 0).toFixed(1)}s–{Number(ov.end ?? 0).toFixed(1)}s
                                {ov.slot_id ? ` · slot ${ov.slot_id}` : ""}
                                {ov.detected_text ? ` · detected: “${ov.detected_text}”` : ""}
                              </div>
                              <div style={{ display: "grid", gridTemplateColumns: "1fr 140px", gap: 8 }}>
                                <input
                                  className="field-input"
                                  value={String(ov.render_text || "")}
                                  onChange={(e) => {
                                    const next = normalizeTextOverlays((currentState as any)?.text_overlays);
                                    next[idx] = { ...next[idx], render_text: e.target.value };
                                    updateState({ ...(currentState as any), text_overlays: next });
                                  }}
                                  placeholder="Final overlay text to render"
                                />
                                <select
                                  className="field-input field-select"
                                  value={String(ov.action || "ask_user")}
                                  onChange={(e) => {
                                    const next = normalizeTextOverlays((currentState as any)?.text_overlays);
                                    next[idx] = { ...next[idx], action: e.target.value };
                                    const stillAsking = next.some(
                                      (x: any) =>
                                        String(x.action || "ask_user").toLowerCase() === "ask_user"
                                    );
                                    updateState({
                                      ...(currentState as any),
                                      text_overlays: next,
                                      text_overlays_resolved: !stillAsking,
                                    });
                                  }}
                                >
                                  <option value="ask_user">ask</option>
                                  <option value="render">render</option>
                                  <option value="keep">keep</option>
                                  <option value="remove">remove</option>
                                </select>
                              </div>
                            </div>
                          )
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <AnimatePresence>
        {finalReport && (
          <motion.div
            className="final-report"
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -18 }}
          >
            <div className="flex items-center gap-2 mb-3">
              <Sparkles size={16} className="text-amber-400" />
              <h3 className="text-sm font-semibold">Final Video Brief</h3>
            </div>
            <div className="final-report-body">{finalReport}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
};
