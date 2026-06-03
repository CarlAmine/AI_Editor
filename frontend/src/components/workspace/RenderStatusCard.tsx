import { CheckCircle2, Clock3, Play, Settings2, Video } from "lucide-react";
import type { TextReplacementEntry } from "../../types/pipeline";

type Props = {
  state: Record<string, unknown>;
  onConfirm: () => void;
  onEdit?: () => void;
  isSubmitting?: boolean;
  generationMode?: string;
};

export function RenderStatusCard({
  state,
  onConfirm,
  onEdit,
  isSubmitting = false,
  generationMode,
}: Props) {
  const isNeural = generationMode === "neural_style_transfer";

  const sources = Array.isArray(state.sources) ? state.sources : [];
  const referenceSlots = Array.isArray(state.reference_slots) ? state.reference_slots : [];
  const slotMapping = Array.isArray(state.slot_mapping) ? state.slot_mapping : [];
  const textReplacements = Array.isArray(state.text_replacements)
    ? (state.text_replacements as TextReplacementEntry[])
    : [];

  const readyToSubmit = isNeural
    ? sources.length >= 1
    : referenceSlots.length > 0 &&
      slotMapping.every((row) => String((row as Record<string, unknown>).clip_url || "").trim()) &&
      textReplacements.every(
        (row) => row.action !== "replace" || String(row.text || "").trim().length > 0,
      );

  return (
    <section className="workspace-card workspace-form-card">
      <div className="workspace-card-header">
        <div>
          <p className="workspace-section-label" style={{ marginBottom: 4 }}>
            {isNeural ? "Neural style transfer" : "Render status"}
          </p>
          <h3 className="workspace-card-title">
            {isNeural ? "Ready to train and render" : "Submission readiness"}
          </h3>
        </div>
        <span className={readyToSubmit ? "workspace-status-pill" : "workspace-status-pill muted"}>
          {readyToSubmit ? "Ready" : "Incomplete"}
        </span>
      </div>

      <div className="workspace-status-stack">
        {isNeural ? (
          <>
            <div className="workspace-status-row">
              <Video size={14} />
              <span>Donor video: {state.primary_url ? "✓ received" : "missing"}</span>
            </div>
            <div className="workspace-status-row">
              <CheckCircle2 size={14} />
              <span>
                Content clips: {sources.length} provided
                {referenceSlots.length > 0 ? ` of ${referenceSlots.length} needed` : ""}
              </span>
            </div>
          </>
        ) : (
          <>
            <div className="workspace-status-row">
              <Clock3 size={14} />
              <span>Reference slots: {referenceSlots.length}</span>
            </div>
            <div className="workspace-status-row">
              <CheckCircle2 size={14} />
              <span>
                Slot URLs filled:{" "}
                {
                  slotMapping.filter((row) =>
                    String((row as Record<string, unknown>).clip_url || "").trim(),
                  ).length
                }
              </span>
            </div>
            <div className="workspace-status-row">
              <Settings2 size={14} />
              <span>Text replacements: {textReplacements.length}</span>
            </div>
          </>
        )}
      </div>

      <div className="workspace-form-actions">
        <button
          type="button"
          className="workspace-btn-primary"
          onClick={onConfirm}
          disabled={!readyToSubmit || isSubmitting}
        >
          <Play size={16} />
          {isSubmitting ? "Submitting…" : isNeural ? "Start training" : "Confirm and render"}
        </button>
        {!isNeural && onEdit && (
          <button
            type="button"
            className="workspace-btn-ghost"
            onClick={onEdit}
            disabled={isSubmitting}
          >
            Edit plan
          </button>
        )}
      </div>
    </section>
  );
}
