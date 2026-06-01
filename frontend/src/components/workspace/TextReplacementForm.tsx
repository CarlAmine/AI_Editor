import { Check, Trash2 } from "lucide-react";
import type { TextReplacementAction, TextReplacementEntry } from "../../types/pipeline";

type Props = {
  rows: TextReplacementEntry[];
  onChange: (nextRows: TextReplacementEntry[]) => void;
  onContinue: () => void;
  onClear: () => void;
};

const ACTION_LABELS: Record<TextReplacementAction, string> = {
  keep: "Keep original text",
  remove: "Remove text",
  replace: "Replace with custom text",
};

export function TextReplacementForm({ rows, onChange, onContinue, onClear }: Props) {
  const updateRow = (index: number, patch: Partial<TextReplacementEntry>) => {
    onChange(
      rows.map((row, rowIndex) => {
        if (rowIndex !== index) return row;
        const next = { ...row, ...patch };
        if (next.action === "remove") {
          next.text = "";
        } else if (next.action === "keep") {
          next.text = next.detectedText;
        }
        return next;
      }),
    );
  };

  if (rows.length === 0) {
    return (
      <section className="workspace-card workspace-form-card">
        <div className="workspace-card-header">
          <div>
            <p className="workspace-section-label" style={{ marginBottom: 4 }}>
              Text replacement
            </p>
            <h3 className="workspace-card-title">Detected text moments</h3>
          </div>
        </div>
        <p className="workspace-muted-copy">No on-screen text was detected in this reference.</p>
      </section>
    );
  }

  return (
    <section className="workspace-card workspace-form-card">
      <div className="workspace-card-header">
        <div>
          <p className="workspace-section-label" style={{ marginBottom: 4 }}>
            Text replacement
          </p>
          <h3 className="workspace-card-title">Detected text moments</h3>
        </div>
      </div>

      <div className="workspace-table-wrap">
        <table className="workspace-table">
          <thead>
            <tr>
              <th>Text moment</th>
              <th>Time range</th>
              <th>Detected text</th>
              <th>Action</th>
              <th>Replacement text</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={row.id}>
                <td>{index + 1}</td>
                <td>
                  {row.start.toFixed(2)}s - {row.end.toFixed(2)}s
                </td>
                <td>{row.detectedText || "No text detected"}</td>
                <td>
                  <select
                    value={row.action}
                    onChange={(event) => {
                      const action = event.target.value as TextReplacementAction;
                      updateRow(index, {
                        action,
                        text: action === "keep" ? row.detectedText : action === "remove" ? "" : row.text,
                      });
                    }}
                    aria-label={`Text action for moment ${index + 1}`}
                  >
                    {Object.entries(ACTION_LABELS).map(([action, label]) => (
                      <option key={action} value={action}>
                        {label}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <input
                    value={row.text}
                    onChange={(event) => updateRow(index, { text: event.target.value, action: "replace" })}
                    placeholder="Replacement text"
                    disabled={row.action !== "replace"}
                    aria-label={`Replacement text for moment ${index + 1}`}
                  />
                </td>
              </tr>
            ))}
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
