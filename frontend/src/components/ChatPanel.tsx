import React, {
  useState,
  FormEvent,
  useEffect,
  useRef,
  KeyboardEvent,
} from "react";
import { AnimatePresence, motion } from "framer-motion";
import { RotateCcw, Send, Sparkles } from "lucide-react";

type Props = {
  apiBase: string;
  analyzerOutput: string;
  currentState?: Record<string, unknown>;
  onStateUpdate?: (state: Record<string, unknown>) => void;
  assistantEvent?: AssistantEvent | null;
  activeJobId?: string | null;
  activeJobStatusCategory?: string | null;
  onPipelineResult?: (result: Record<string, unknown>) => void;
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

type ResumeTarget = {
  endpoint: string;
  isResume: boolean;
};

export function resolveChatSubmitTarget(
  apiBase: string,
  jobStatusCategory?: string | null,
  jobId?: string | null
): ResumeTarget {
  if (
    jobId &&
    (jobStatusCategory === "waiting_for_user_input" ||
      jobStatusCategory === "blocked")
  ) {
    return {
      endpoint: `${apiBase}/jobs/${jobId}/resume`,
      isResume: true,
    };
  }
  return {
    endpoint: `${apiBase}/chat`,
    isResume: false,
  };
}

type Message = {
  id: number;
  from: "user" | "assistant";
  text: string;
  timestamp: Date;
};

function SyntaxHighlightedJSON({ value }: { value: Record<string, unknown> }) {
  const lines = JSON.stringify(value, null, 2).split("\n");
  return (
    <pre className="state-preview">
      {lines.map((line, i) => {
        const keyMatch = line.match(/^(\s*)("[\w\s]+")\s*:/);
        const strValMatch = line.match(/:\s*(".*")(,?)$/);
        const numValMatch = line.match(/:\s*(-?\d+\.?\d*)(,?)$/);
        const boolValMatch = line.match(/:\s*(true|false|null)(,?)$/);

        if (keyMatch) {
          const indent = keyMatch[1];
          const key = keyMatch[2];
          const rest = line.slice(keyMatch[0].length);
          let valueNode: React.ReactNode = rest;

          if (strValMatch) {
            valueNode = (
              <>
                {": "}
                <span className="json-string">{strValMatch[1]}</span>
                {strValMatch[2]}
              </>
            );
          } else if (numValMatch) {
            valueNode = (
              <>
                {": "}
                <span className="json-number">{numValMatch[1]}</span>
                {numValMatch[2]}
              </>
            );
          } else if (boolValMatch) {
            valueNode = (
              <>
                {": "}
                <span className="json-boolean">{boolValMatch[1]}</span>
                {boolValMatch[2]}
              </>
            );
          }

          return (
            <span key={i}>
              {indent}
              <span className="json-key">{key}</span>
              {valueNode}
              {"\n"}
            </span>
          );
        }

        return (
          <span key={i}>
            {line}
            {"\n"}
          </span>
        );
      })}
    </pre>
  );
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
}) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [currentState, setCurrentState] =
    useState<Record<string, unknown>>(externalState);
  const [isLoading, setIsLoading] = useState(false);
  const [finalReport, setFinalReport] = useState<string | null>(null);
  const [showState, setShowState] = useState(false);
  const lastAssistantEventId = useRef<number | null>(null);
  const chatWindowRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setCurrentState(externalState || {});
  }, [externalState]);

  useEffect(() => {
    if (chatWindowRef.current) {
      chatWindowRef.current.scrollTop = chatWindowRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

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
    setShowState(false);
    updateState({});
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userText = input.trim();
    appendMessage("user", userText);
    setInput("");
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
                Start by telling the assistant what kind of video you&apos;re
                creating, for example:
              </p>
              <ul className="space-y-2">
                <li className="text-sm text-gray-400">
                  &ldquo;I need a 60s TikTok ad for a fitness app aimed at busy
                  professionals.&rdquo;
                </li>
                <li className="text-sm text-gray-400">
                  &ldquo;Make a YouTube explainer for beginners about my AI
                  editor.&rdquo;
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
          onClick={() => setShowState((v) => !v)}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
        >
          {showState ? "Hide Fields" : "Show Collected Fields"}
        </motion.button>
        <AnimatePresence>
          {showState && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.25 }}
            >
              <SyntaxHighlightedJSON value={currentState} />
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
