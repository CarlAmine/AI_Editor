import {
  normalizeSources,
  normalizeTextOverlays,
} from "../../hooks/useWorkspaceChat";

type Props = {
  currentState: Record<string, unknown>;
  onUpdate: (state: Record<string, unknown>) => void;
};

export function ProjectFieldsPanel({ currentState, onUpdate }: Props) {
  const state = currentState as Record<string, unknown>;

  return (
    <div className="workspace-fields-panel">
      <div className="workspace-field">
        <label htmlFor="ws-primary-url">Reference URL</label>
        <input
          id="ws-primary-url"
          value={String(state.primary_url || "")}
          onChange={(e) => onUpdate({ ...state, primary_url: e.target.value })}
          placeholder="https://www.youtube.com/watch?v=..."
        />
      </div>

      <div className="workspace-field">
        <label htmlFor="ws-drive-link">Google Drive folder (optional)</label>
        <input
          id="ws-drive-link"
          value={String(state.google_drive_link || "")}
          onChange={(e) => onUpdate({ ...state, google_drive_link: e.target.value })}
          placeholder="https://drive.google.com/drive/folders/..."
        />
      </div>

      <div className="workspace-field">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <label style={{ margin: 0 }}>Replacement clip URLs</label>
          <button
            type="button"
            className="workspace-btn-ghost"
            onClick={() => {
              const next = normalizeSources(state.sources);
              next.push({ url: "", label: next.length + 1 });
              onUpdate({ ...state, sources: next });
            }}
          >
            Add URL
          </button>
        </div>
        {normalizeSources(state.sources).length === 0 ? (
          <p style={{ fontSize: 12, color: "var(--ws-text-muted)", margin: "6px 0 0" }}>
            Add one URL per replacement slot.
          </p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 8 }}>
            {normalizeSources(state.sources).map((src, idx) => (
              <div key={idx} style={{ display: "flex", gap: 8 }}>
                <input
                  value={src.url}
                  onChange={(e) => {
                    const next = normalizeSources(state.sources);
                    next[idx] = { ...next[idx], url: e.target.value, label: idx + 1 };
                    onUpdate({ ...state, sources: next });
                  }}
                  placeholder={`Clip URL ${idx + 1}`}
                />
                <button
                  type="button"
                  className="workspace-btn-ghost"
                  onClick={() => {
                    const next = normalizeSources(state.sources).filter((_, i) => i !== idx);
                    onUpdate({ ...state, sources: next });
                  }}
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="workspace-field" style={{ marginBottom: 0 }}>
        <label>Overlay text (per sequence)</label>
        {normalizeTextOverlays(state.text_overlays).length === 0 ? (
          <p style={{ fontSize: 12, color: "var(--ws-text-muted)", margin: "6px 0 0" }}>
            Overlays appear here after reference analysis.
          </p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 8 }}>
            {normalizeTextOverlays(state.text_overlays).map((ov, idx) => (
              <div
                key={String(ov.overlay_id || `${idx}-${ov.start}-${ov.end}`)}
                style={{
                  padding: 10,
                  border: "1px solid var(--ws-border)",
                  borderRadius: 8,
                  background: "var(--ws-bg)",
                }}
              >
                <p style={{ fontSize: 11, color: "var(--ws-text-subtle)", margin: "0 0 8px" }}>
                  {Number(ov.start ?? 0).toFixed(1)}s–{Number(ov.end ?? 0).toFixed(1)}s
                  {ov.slot_id != null ? ` · slot ${ov.slot_id}` : ""}
                  {ov.detected_text ? ` · detected: ${String(ov.detected_text)}` : ""}
                </p>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 120px", gap: 8 }}>
                  <input
                    value={String(ov.render_text || "")}
                    onChange={(e) => {
                      const next = normalizeTextOverlays(state.text_overlays);
                      next[idx] = { ...next[idx], render_text: e.target.value };
                      onUpdate({ ...state, text_overlays: next });
                    }}
                    placeholder="Final overlay text"
                  />
                  <select
                    value={String(ov.action || "ask_user")}
                    onChange={(e) => {
                      const next = normalizeTextOverlays(state.text_overlays);
                      next[idx] = { ...next[idx], action: e.target.value };
                      const stillAsking = next.some(
                        (x) => String(x.action || "ask_user").toLowerCase() === "ask_user"
                      );
                      onUpdate({
                        ...state,
                        text_overlays: next,
                        text_overlays_resolved: !stillAsking,
                      });
                    }}
                  >
                    <option value="ask_user">Pending</option>
                    <option value="render">Render</option>
                    <option value="keep">Keep</option>
                    <option value="remove">Remove</option>
                  </select>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
