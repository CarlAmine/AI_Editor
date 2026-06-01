import React from "react";
import { Film, Info } from "lucide-react";
import { ReferenceSummary, ReferenceSlot } from "../types/pipeline";

type Props = {
  summary: ReferenceSummary;
  slots: ReferenceSlot[];
};

export const ReferenceSummaryCard: React.FC<Props> = ({ summary, slots }) => {
  return (
    <section className="workspace-card" style={{ margin: "1rem 0" }}>
      <div className="workspace-card-header">
        <div>
          <p className="workspace-section-label" style={{ marginBottom: 4 }}>
            Reference analysis
          </p>
          <h3 className="workspace-card-title">Style summary and slot breakdown</h3>
        </div>
        <span className="workspace-status-pill">Ready</span>
      </div>

      <div className="workspace-metric-grid">
        <div className="workspace-metric">
          <Film size={16} />
          <div>
            <span>Duration</span>
            <strong>{summary.duration_seconds}s</strong>
          </div>
        </div>
        <div className="workspace-metric">
          <Info size={16} />
          <div>
            <span>Format</span>
            <strong>{summary.aspect_ratio}</strong>
          </div>
        </div>
        <div className="workspace-metric">
          <Film size={16} />
          <div>
            <span>FPS</span>
            <strong>{summary.fps}</strong>
          </div>
        </div>
        <div className="workspace-metric">
          <Info size={16} />
          <div>
            <span>Slots</span>
            <strong>{slots.length}</strong>
          </div>
        </div>
      </div>

      <div className="workspace-summary-block">
        <span>Style notes</span>
        <p>{summary.style_summary}</p>
      </div>

      <div className="workspace-table-wrap" style={{ marginTop: 16 }}>
        <table className="workspace-table">
          <thead>
            <tr>
              <th>Slot</th>
              <th>Role</th>
              <th>Duration</th>
              <th>Time range</th>
            </tr>
          </thead>
          <tbody>
            {slots.map((slot) => (
              <tr key={slot.slot_id}>
                <td>Slot {slot.slot_id}</td>
                <td>
                  <span className="workspace-tag">{slot.role}</span>
                </td>
                <td>{slot.duration}s</td>
                <td>
                  {slot.start_time}s - {slot.end_time}s
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
};
