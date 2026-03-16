import React, { useState, FormEvent, useEffect, useRef, KeyboardEvent } from "react";
import { Send } from "lucide-react";

type Props = {
  apiBase: string;
  analyzerOutput: string;
  onStateUpdate?: (state: Record<string, unknown>) => void;
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
};

/** Render JSON with simple syntax highlighting (no external library) */
function SyntaxHighlightedJSON({ value }: { value: Record<string, unknown> }) {
  const lines = JSON.stringify(value, null, 2).split("\n");
  return (
    <pre className="state-preview">
      {lines.map((line, i) => {
        // Key: "someKey":
        const keyMatch = line.match(/^(\s*)("[\w\s]+")\s*:/);
        // String value
        const strValMatch = line.match(/:\s*(".*")(,?)$/);
        // Number value
        const numValMatch = line.match(/:\s*(-?\d+\.?\d*)(,?)$/);
        // Boolean/null value
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

        return <span key={i}>{line}{"\n"}</span>;
      })}
    </pre>
  );
}

export const ChatPanel: React.FC<Props> = ({ apiBase, analyzerOutput, onStateUpdate }) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [currentState, setCurrentState] = useState<Record<string, unknown>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [finalReport, setFinalReport] = useState<string | null>(null);
  const [showState, setShowState] = useState(false);

  // Bug fix #4: auto-scroll ref
  const chatWindowRef = useRef<HTMLDivElement>(null);

  // Bug fix #4: scroll to bottom whenever messages change
  useEffect(() => {
    if (chatWindowRef.current) {
      chatWindowRef.current.scrollTop = chatWindowRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const updateState = (newState: Record<string, unknown>) => {
    setCurrentState(newState);
    if (onStateUpdate) {
      onStateUpdate(newState);
    }
  };

  const appendMessage = (from: "user" | "assistant", text: string) => {
    setMessages((prev) => [
      ...prev,
      { id: Date.now() + Math.random(), from, text },
    ]);
  };

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

    try {
      const response = await fetch(`${apiBase}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data: ChatTurnResponse = await response.json();

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

  // Bug fix #5: Enter (without Shift) submits the form
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
        <h2 className="panel-title">Brief the Assistant</h2>
        <p className="panel-caption">
          Refine the creative brief through a short conversation. The assistant
          tracks requirements and produces a final written brief.
        </p>
      </header>

      {/* Bug fix #4: ref on chat window */}
      <div className="chat-window" ref={chatWindowRef}>
        {messages.length === 0 && (
          <div className="chat-empty">
            <p>
              Start by telling the assistant what kind of video you&apos;re
              creating, for example:
            </p>
            <ul>
              <li>
                &ldquo;I need a 60s TikTok ad for a fitness app aimed at busy
                professionals.&rdquo;
              </li>
              <li>
                &ldquo;Make a YouTube explainer for beginners about my AI
                editor.&rdquo;
              </li>
            </ul>
          </div>
        )}
        {messages.map((m) => (
          <div
            key={m.id}
            className={
              m.from === "user" ? "chat-bubble chat-bubble-user" : "chat-bubble chat-bubble-assistant"
            }
          >
            <span className="chat-author">
              {m.from === "user" ? "You" : "Assistant"}
            </span>
            <p className="chat-text">{m.text}</p>
          </div>
        ))}
        {/* Typing indicator instead of plain "Thinking..." */}
        {isLoading && (
          <div className="chat-bubble chat-bubble-assistant">
            <span className="chat-author">Assistant</span>
            <div className="typing-indicator">
              <span className="typing-dot" />
              <span className="typing-dot" />
              <span className="typing-dot" />
            </div>
          </div>
        )}
      </div>

      {/* Bug fix #5: textarea with onKeyDown */}
      <form className="chat-input-row" onSubmit={handleSubmit}>
        <textarea
          className="field-input chat-input"
          placeholder="Type your next message... (Enter to send, Shift+Enter for new line)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
        />
        <button className="btn btn-primary chat-send" disabled={isLoading} type="submit">
          <Send size={16} />
        </button>
      </form>

      <div className="chat-meta">
        <button
          type="button"
          className="btn btn-ghost"
          onClick={handleClearChat}
          disabled={isLoading}
        >
          Clear Chat
        </button>
        {/* "Show Collected Fields" as a pill badge */}
        <button
          type="button"
          className="btn btn-pill"
          onClick={() => setShowState((v) => !v)}
        >
          {showState ? "Hide Fields" : "Show Collected Fields"}
        </button>
        {showState && (
          <SyntaxHighlightedJSON value={currentState} />
        )}
      </div>

      {finalReport && (
        <div className="final-report">
          <h3>Final Video Brief</h3>
          <div className="final-report-body">{finalReport}</div>
        </div>
      )}
    </section>
  );
};
