import { CheckCircle2, Clock3, Play, Settings2 } from "lucide-react";
import type { TextReplacementEntry } from "../../types/pipeline";

type Props = {
  state: Record<string, unknown>;
  onConfirm: () => void;
  onEdit: () => void;
  isSubmitting?: boolean;
};

export function RenderStatusCard({ state, onConfirm, onEdit, isSubmitting = false }: Props) {
  const slotMapping = Array.isArray(state.slot_mapping) ? state.slot_mapping : [];
  const referenceSlots = Array.isArray(state.reference_slots) ? state.reference_slots : [];
  const textReplacements = Array.isArray(state.text_replacements)
    ? (state.text_replacements as TextReplacementEntry[])
    : [];
  const readyToSubmit =
    referenceSlots.length > 0 &&
    slotMapping.every((row) => String((row as Record<string, unknown>).clip_url || "").trim()) &&
    textReplacements.every(
      (row) => row.action !== "replace" || String(row.text || "").trim().length > 0,
    );

  return (
    <section className="workspace-card workspace-form-card">
      <div className="workspace-card-header">
        <div>
          <p className="workspace-section-label" style={{ marginBottom: 4 }}>
            Render status
          </p>
          <h3 className="workspace-card-title">Submission readiness</h3>
        </div>
        <span className={readyToSubmit ? "workspace-status-pill" : "workspace-status-pill muted"}>
          {readyToSubmit ? "Ready" : "Incomplete"}
        </span>
      </div>

      <div className="workspace-status-stack">
        <div className="workspace-status-row">
          <Clock3 size={14} />
          <span>Reference slots: {referenceSlots.length}</span>
        </div>
        <div className="workspace-status-row">
          <CheckCircle2 size={14} />
          <span>
            Slot URLs filled:{" "}
            {slotMapping.filter((row) => String((row as Record<string, unknown>).clip_url || "").trim())
              .length}
          </span>
        </div>
        <div className="workspace-status-row">
          <Settings2 size={14} />
          <span>Text replacements: {textReplacements.length}</span>
        </div>
      </div>

      <div className="workspace-form-actions">
        <button type="button" className="workspace-btn-primary" onClick={onConfirm} disabled={!readyToSubmit || isSubmitting}>
          <Play size={16} />
          {isSubmitting ? "Submitting" : "Confirm and render"}
        </button>
        <button type="button" className="workspace-btn-ghost" onClick={onEdit} disabled={isSubmitting}>
          Edit plan
        </button>
      </div>
    </section>
  );
}
