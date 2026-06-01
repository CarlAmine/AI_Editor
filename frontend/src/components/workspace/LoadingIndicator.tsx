export function LoadingIndicator() {
  return (
    <article className="workspace-msg-assistant" style={{ marginBottom: 20 }}>
      <div className="workspace-msg-meta">Assistant</div>
      <div className="workspace-card">
        <div className="workspace-typing" aria-label="Assistant is typing">
          <span />
          <span />
          <span />
        </div>
      </div>
    </article>
  );
}
