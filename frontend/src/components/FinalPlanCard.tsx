import React from "react";
import { Check, Edit, Music, Monitor, HardDrive, Play } from "lucide-react";

type Props = {
  state: Record<string, any>;
  onConfirm: () => void;
  onEdit: () => void;
  isSubmitting?: boolean;
};

export const FinalPlanCard: React.FC<Props> = ({ state, onConfirm, onEdit, isSubmitting = false }) => {
  const referenceSlots: Array<Record<string, any>> = Array.isArray(state.reference_slots)
    ? state.reference_slots
    : [];
  const slotMapping: Array<Record<string, any>> = Array.isArray(state.slot_mapping)
    ? state.slot_mapping
    : [];
  const googleDrive = typeof state.google_drive_link === "string" ? state.google_drive_link : "";
  const textOverlays: Array<Record<string, any>> = Array.isArray(state.text_overlays)
    ? state.text_overlays
    : [];
  const renderableOverlays = textOverlays.filter(
    (overlay) =>
      ["render", "keep"].includes(String(overlay.action || "").toLowerCase()) &&
      String(overlay.render_text || overlay.detected_text || "").trim(),
  );

  const formatClipUrl = (url: string) => {
    if (!url) return "Not assigned";
    if (url.length > 30) {
      try {
        const parsed = new URL(url);
        return `${parsed.hostname}...${parsed.pathname.substring(0, 10)}`;
      } catch {
        return `${url.substring(0, 25)}...`;
      }
    }
    return url;
  };

  return (
    <section className="workspace-card" style={{ margin: "1rem 0" }}>
      <div className="workspace-card-header">
        <div>
          <p className="workspace-section-label" style={{ marginBottom: 4 }}>
            Render plan
          </p>
          <h3 className="workspace-card-title">Ready to render</h3>
        </div>
        <span className="workspace-status-pill">Review</span>
      </div>

      <div className="workspace-summary-block" style={{ marginBottom: 16 }}>
        <span>Reference video</span>
        {state.primary_url ? (
          <a href={state.primary_url} target="_blank" rel="noopener noreferrer" style={{ color: "#e2e8f0", wordBreak: "break-all" }}>
            {state.primary_url}
          </a>
        ) : (
          <p>No reference URL has been provided yet.</p>
        )}
      </div>

      <div style={{ marginBottom: "1.25rem" }}>
        <div className="workspace-card-header" style={{ marginBottom: 10 }}>
          <div>
            <p className="workspace-section-label" style={{ marginBottom: 4 }}>
              Replacement plan
            </p>
            <h4 className="workspace-card-title" style={{ fontSize: 16 }}>Slot assignments</h4>
          </div>
          <HardDrive size={16} color="#94a3b8" />
        </div>

        {googleDrive ? (
          <div className="workspace-summary-block">
            <span>Google Drive folder</span>
            <p>Drive folder intake is enabled.</p>
            <a href={googleDrive} target="_blank" rel="noopener noreferrer" style={{ color: "#e2e8f0", wordBreak: "break-all" }}>
              {googleDrive}
            </a>
          </div>
        ) : referenceSlots.length === 0 ? (
          <div className="workspace-summary-block">
            <p>No replacement slots have been detected yet.</p>
          </div>
        ) : (
          <div className="workspace-table-wrap">
            <table className="workspace-table">
              <thead>
                <tr>
                  <th>Slot</th>
                  <th>Role</th>
                  <th>Replacement URL</th>
                </tr>
              </thead>
              <tbody>
                {referenceSlots.map((slot: any) => {
                  const mapping = slotMapping.find((entry: any) => entry.slot_id === slot.slot_id);
                  return (
                    <tr key={slot.slot_id}>
                      <td>Slot {slot.slot_id}</td>
                      <td>
                        <span className="workspace-tag">{slot.role}</span>
                      </td>
                      <td style={{ color: mapping ? "#e2e8f0" : "#f87171" }}>
                        {mapping ? formatClipUrl(mapping.clip_url) : "Unassigned"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div style={{ marginBottom: "1.25rem" }}>
        <div className="workspace-card-header" style={{ marginBottom: 10 }}>
          <div>
            <p className="workspace-section-label" style={{ marginBottom: 4 }}>
              Text replacements
            </p>
            <h4 className="workspace-card-title" style={{ fontSize: 16 }}>Overlay decisions</h4>
          </div>
          <Music size={16} color="#94a3b8" />
        </div>

        {textOverlays.length === 0 ? (
          <p className="workspace-muted-copy">No text overlays selected.</p>
        ) : renderableOverlays.length === 0 ? (
          <p className="workspace-muted-copy">Detected text was found, but no final overlay text has been selected.</p>
        ) : (
          <div className="workspace-table-wrap">
            <table className="workspace-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Slot</th>
                  <th>Detected Text</th>
                  <th>Final Text</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {textOverlays.map((overlay: any) => (
                  <tr key={overlay.overlay_id || `${overlay.start}-${overlay.end}`}>
                    <td>
                      {Number(overlay.start ?? 0).toFixed(1)}s - {Number(overlay.end ?? 0).toFixed(1)}s
                    </td>
                    <td>{overlay.slot_id ?? "-"}</td>
                    <td>{overlay.detected_text || "-"}</td>
                    <td>
                      {overlay.render_text ||
                        (["render", "keep"].includes(String(overlay.action || "").toLowerCase())
                          ? overlay.detected_text
                          : "-")}
                    </td>
                    <td style={{ textTransform: "uppercase", fontSize: "0.75rem", color: "#94a3b8" }}>
                      {overlay.action || "ask_user"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="workspace-metric-grid" style={{ marginBottom: 16 }}>
        <div className="workspace-metric">
          <Music size={14} />
          <div>
            <span>Audio</span>
            <strong>{state.music_mode === "custom" ? "Custom track" : "Original reference audio"}</strong>
          </div>
        </div>
        <div className="workspace-metric">
          <Monitor size={14} />
          <div>
            <span>Format</span>
            <strong>
              {state.aspect_ratio || "Not specified"} ({state.refit_mode === "pad" ? "Pad" : "Crop"})
            </strong>
          </div>
        </div>
      </div>

      <div className="workspace-form-actions">
        <button
          onClick={onConfirm}
          disabled={isSubmitting}
          className="workspace-btn-primary"
          type="button"
        >
          <Play size={16} />
          {isSubmitting ? "Submitting..." : "Confirm and render"}
        </button>
        <button
          onClick={onEdit}
          disabled={isSubmitting}
          className="workspace-btn-ghost"
          type="button"
        >
          <Edit size={16} />
          Edit plan
        </button>
      </div>
    </section>
  );
};
