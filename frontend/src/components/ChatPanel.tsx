import React, { useState, FormEvent } from "react";

type Props = {
  apiBase: string;
  analyzerOutput: string;
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

export const ChatPanel: React.FC<Props> = ({ apiBase, analyzerOutput }) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [currentState, setCurrentState] = useState<Record<string, unknown>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [finalReport, setFinalReport] = useState<string | null>(null);
  const [showState, setShowState] = useState(false);

  const appendMessage = (from: "user" | "assistant", text: string) => {
    setMessages((prev) => [
      ...prev,
      { id: Date.now() + Math.random(), from, text },
    ]);
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
        setCurrentState(data.updated_state);
      }

      if (data.next_message) {
        appendMessage("assistant", data.next_message);
      }

      if (data.is_complete && data.final_report) {
        setFinalReport(data.final_report);
      }
    } catch (err: any) {
      appendMessage(
        "assistant",
        err?.message || "Something went wrong talking to the chat endpoint."
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <section className="panel">
      <header className="panel-header">
        <h2 className="panel-title">2. Brief With the Producer</h2>
        <p className="panel-caption">
          Refine the creative brief through a short conversation. The assistant
          tracks requirements and produces a final written brief.
        </p>
      </header>

      <div className="chat-window">
        {messages.length === 0 && (
          <div className="chat-empty">
            <p>
              Start by telling the assistant what kind of video you&apos;re
              creating — for example:
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
              m.from === "user" ? "chat-bubble chat-bubble-user" : "chat-bubble"
            }
          >
            <span className="chat-author">
              {m.from === "user" ? "You" : "Assistant"}
            </span>
            <p className="chat-text">{m.text}</p>
          </div>
        ))}
        {isLoading && (
          <div className="chat-bubble">
            <span className="chat-author">Assistant</span>
            <p className="chat-text">Thinking…</p>
          </div>
        )}
      </div>

      <form className="chat-input-row" onSubmit={handleSubmit}>
        <input
          className="field-input chat-input"
          placeholder="Type your next message…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <button className="btn btn-primary chat-send" disabled={isLoading}>
          Send
        </button>
      </form>

      <div className="chat-meta">
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => setShowState((v) => !v)}
        >
          {showState ? "Hide collected fields" : "Show collected fields"}
        </button>
        {showState && (
          <pre className="state-preview">
            {JSON.stringify(currentState, null, 2)}
          </pre>
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

