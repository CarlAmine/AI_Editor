import { useEffect, useState } from "react";
import { usePipelineJob } from "../hooks/usePipelineJob";
import { useWorkspaceChat } from "../hooks/useWorkspaceChat";
import { fetchProviderHealth, type ProviderHealthPayload } from "../lib/api";
import { WorkspaceSidebar } from "../components/workspace/WorkspaceSidebar";
import { WorkspaceHeader } from "../components/workspace/WorkspaceHeader";
import { ConversationCanvas } from "../components/workspace/ConversationCanvas";
import { ChatInputDock } from "../components/workspace/ChatInputDock";
import { WorkspaceStatusPanel } from "../components/workspace/WorkspaceStatusPanel";
import type { PipelineResult } from "../components/VideoPipelinePanel";
import "./workspace.css";

export default function Workspace() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [providerHealth, setProviderHealth] = useState<ProviderHealthPayload | null>(null);

  const {
    apiBase,
    briefState,
    setBriefState,
    displayResult,
    isPolling,
    handleRenderResult,
    submitChatPipelinePayload,
  } = usePipelineJob();

  const chat = useWorkspaceChat({
    apiBase,
    externalState: briefState,
    onStateUpdate: setBriefState,
    activeJobId: displayResult?.project_id || null,
    activeJobStatusCategory: displayResult?.controller_status_category || null,
    onPipelineResult: (result) => handleRenderResult(result as PipelineResult | null),
    onSubmitPipelinePayload: submitChatPipelinePayload,
  });

  useEffect(() => {
    void fetchProviderHealth(apiBase)
      .then(setProviderHealth)
      .catch(() => setProviderHealth({ success: false, ready: false, providers: {} }));
  }, [apiBase]);

  const chatState = chat.currentState as Record<string, unknown>;

  return (
    <div className="workspace-root">
      <WorkspaceSidebar
        open={sidebarOpen}
        onToggle={() => setSidebarOpen((v) => !v)}
        providerHealth={providerHealth}
        showFieldsEditor={chat.showFieldsEditor}
        onToggleFieldsEditor={() => chat.setShowFieldsEditor((v) => !v)}
        onClearSession={chat.handleClearChat}
      />

      <div className="workspace-main">
        <WorkspaceHeader
          isPolling={isPolling}
          projectId={displayResult?.project_id}
          phase={String(chatState.phase || "")}
        />

        <div className="workspace-body">
          <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, position: "relative" }}>
            <ConversationCanvas {...chat} chatState={chatState} />
            <ChatInputDock
              value={chat.input}
              onChange={chat.setInput}
              onSubmit={chat.handleSubmit}
              onKeyDown={chat.handleKeyDown}
              disabled={chat.isLoading}
            />
          </div>

          <aside className="workspace-rail">
            <WorkspaceStatusPanel apiBase={apiBase} result={displayResult} isPolling={isPolling} />
          </aside>
        </div>
      </div>
    </div>
  );
}
