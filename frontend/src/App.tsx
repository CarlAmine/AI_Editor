import React, { useState } from "react";
import { ChatPanel } from "./components/ChatPanel";
import { VideoPipelinePanel } from "./components/VideoPipelinePanel";

const apiBase =
  import.meta.env.VITE_API_BASE_URL?.toString().replace(/\/$/, "") ||
  "http://localhost:10000";

export const App: React.FC = () => {
  const [analyzerOutput, setAnalyzerOutput] = useState<string>("");

  return (
    <div className="app-root">
      <header className="app-header">
        <div className="app-title-block">
          <h1 className="app-title">AI Editor Studio</h1>
          <p className="app-subtitle">
            Analyze raw footage, capture requirements, and render polished edits
            — all from one interface.
          </p>
        </div>
        <div className="app-badge-row">
          <span className="app-badge">FastAPI · React · Groq · Shotstack</span>
        </div>
      </header>

      <main className="app-main">
        <section className="app-grid">
          <VideoPipelinePanel apiBase={apiBase} onAnalyzerSummary={setAnalyzerOutput} />
          <ChatPanel apiBase={apiBase} analyzerOutput={analyzerOutput} />
        </section>
      </main>

      <footer className="app-footer">
        <span>Backend API: {apiBase}</span>
      </footer>
    </div>
  );
};

export default App;

