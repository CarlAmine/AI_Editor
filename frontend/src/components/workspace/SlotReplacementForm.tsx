import { Check, Trash2 } from "lucide-react";
import type { ReplacementSlot, SlotMappingEntry } from "../../types/pipeline";

type Props = {
  slots: ReplacementSlot[];
  slotMapping: SlotMappingEntry[];
  sameTargetVideo: boolean;
  sharedTargetVideoUrl: string;
  onChange: (nextMapping: SlotMappingEntry[]) => void;
  onToggleSameTargetVideo: (enabled: boolean) => void;
  onSharedTargetVideoUrlChange: (url: string) => void;
  onContinue: () => void;
  onClear: () => void;
};

function ensureSlotMapping(slots: ReplacementSlot[], slotMapping: SlotMappingEntry[]) {
  return slots.map((slot, index) => {
    const existing = slotMapping.find((item) => item.slot_id === slot.slotId);
    return (
      existing || {
        slot_id: slot.slotId,
        clip_id: `slot_${slot.slotId}`,
        clip_url: "",
        source_start: 0,
        source_end: slot.duration || Math.max(0, slot.end - slot.start),
      }
    );
  });
}

export function SlotReplacementForm({
  slots,
  slotMapping,
  sameTargetVideo,
  sharedTargetVideoUrl,
  onChange,
  onToggleSameTargetVideo,
  onSharedTargetVideoUrlChange,
  onContinue,
  onClear,
}: Props) {
  const rows = ensureSlotMapping(slots, slotMapping);
  const sharedValue = sameTargetVideo ? sharedTargetVideoUrl : "";

  const updateRow = (index: number, patch: Partial<SlotMappingEntry>) => {
    const next = rows.map((row, rowIndex) =>
      rowIndex === index ? { ...row, ...patch } : row,
    );
    onChange(next);
  };

  const applySharedUrl = (url: string) => {
    onSharedTargetVideoUrlChange(url);
    onChange(
      rows.map((row) => ({
        ...row,
        clip_url: url,
        clip_id: row.clip_id || `slot_${row.slot_id}`,
      })),
    );
  };

  return (
    <section className="workspace-card workspace-form-card">
      <div className="workspace-card-header">
        <div>
          <p className="workspace-section-label" style={{ marginBottom: 4 }}>
            Slot replacement
          </p>
          <h3 className="workspace-card-title">Replacement clip mapping</h3>
        </div>
        <button
          type="button"
          className="workspace-btn-ghost"
          onClick={() => onToggleSameTargetVideo(!sameTargetVideo)}
        >
          {sameTargetVideo ? "Use separate URLs" : "Use same target video for all slots"}
        </button>
      </div>

      {sameTargetVideo && (
        <div className="workspace-inline-callout">
          <label htmlFor="shared-target-video">Shared replacement video URL</label>
          <input
            id="shared-target-video"
            value={sharedValue}
            onChange={(event) => applySharedUrl(event.target.value)}
            placeholder="https://..."
          />
        </div>
      )}

      <div className="workspace-table-wrap">
        <table className="workspace-table">
          <thead>
            <tr>
              <th>Slot</th>
              <th>Role</th>
              <th>Duration</th>
              <th>Time range</th>
              <th>Replacement URL</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => {
              const slot = slots[index];
              return (
                <tr key={row.slot_id}>
                  <td>Slot {row.slot_id}</td>
                  <td>
                    <span className="workspace-tag">{slot?.role || "b-roll"}</span>
                  </td>
                  <td>{slot ? `${slot.duration.toFixed(2)}s` : `${Number(row.source_end ?? 0).toFixed(2)}s`}</td>
                  <td>
                    {slot ? `${slot.start.toFixed(2)}s - ${slot.end.toFixed(2)}s` : "—"}
                  </td>
                  <td>
                    <div className="workspace-inline-input">
                      <input
                        value={sameTargetVideo ? sharedValue : row.clip_url}
                        onChange={(event) => {
                          const nextValue = event.target.value;
                          if (sameTargetVideo) {
                            applySharedUrl(nextValue);
                            return;
                          }
                          updateRow(index, {
                            clip_url: nextValue,
                            clip_id: row.clip_id || `slot_${row.slot_id}`,
                          });
                        }}
                        placeholder="Paste replacement video URL"
                        aria-label={`Replacement URL for slot ${row.slot_id}`}
                      />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="workspace-form-actions">
        <button type="button" className="workspace-btn-primary" onClick={onContinue}>
          <Check size={16} />
          Continue
        </button>
        <button type="button" className="workspace-btn-ghost" onClick={onClear}>
          <Trash2 size={16} />
          Clear
        </button>
      </div>
    </section>
  );
}
