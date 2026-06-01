import { Clock3, LayoutGrid, Monitor, Sparkles } from "lucide-react";
import type { ReferenceAnalysisSummary, ReplacementSlot } from "../../types/pipeline";

type Props = {
  summary: ReferenceAnalysisSummary;
  slots: ReplacementSlot[];
};

export function StyleSummaryCard({ summary, slots }: Props) {
  return (
    <section className="workspace-card workspace-analysis-card">
      <div className="workspace-card-header">
        <div>
          <p className="workspace-section-label" style={{ marginBottom: 4 }}>
            Style summary
          </p>
          <h3 className="workspace-card-title">Reference analysis</h3>
        </div>
        <span className="workspace-status-pill">Ready</span>
      </div>

      <div className="workspace-metric-grid">
        <div className="workspace-metric">
          <Clock3 size={16} />
          <div>
            <span>Duration</span>
            <strong>{summary.durationSeconds.toFixed(2)}s</strong>
          </div>
        </div>
        <div className="workspace-metric">
          <LayoutGrid size={16} />
          <div>
            <span>Format</span>
            <strong>{summary.aspectRatio}</strong>
          </div>
        </div>
        <div className="workspace-metric">
          <Monitor size={16} />
          <div>
            <span>Resolution</span>
            <strong>
              {summary.width} x {summary.height}
            </strong>
          </div>
        </div>
        <div className="workspace-metric">
          <Sparkles size={16} />
          <div>
            <span>Slots detected</span>
            <strong>{slots.length}</strong>
          </div>
        </div>
      </div>

      <div className="workspace-summary-block">
        <span>Style notes</span>
        <p>{summary.styleSummary}</p>
      </div>
    </section>
  );
}
