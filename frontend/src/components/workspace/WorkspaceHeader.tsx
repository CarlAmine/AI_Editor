import { Link } from "wouter";
import { Loader2 } from "lucide-react";

type Props = {
  isPolling: boolean;
  projectId?: string | null;
  phase?: string;
};

export function WorkspaceHeader({ isPolling, projectId, phase }: Props) {
  return (
    <header className="workspace-header">
      <div style={{ display: "flex", alignItems: "center", gap: 12, minWidth: 0 }}>
        <span style={{ fontSize: 14, fontWeight: 600, color: "var(--ws-text)" }}>
          Editing workspace
        </span>
        {phase && (
          <span
            style={{
              fontSize: 11,
              fontWeight: 500,
              padding: "3px 8px",
              borderRadius: 4,
              background: "var(--ws-accent-muted)",
              color: "var(--ws-text-muted)",
              textTransform: "capitalize",
            }}
          >
            {phase.replace(/_/g, " ")}
          </span>
        )}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        {isPolling && (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: "0.04em",
              textTransform: "uppercase",
              color: "var(--ws-text-muted)",
            }}
          >
            <Loader2 size={12} className="animate-spin" />
            Processing
          </span>
        )}
        {projectId && (
          <span
            style={{
              fontSize: 11,
              fontFamily: "ui-monospace, monospace",
              color: "var(--ws-text-subtle)",
              maxWidth: 140,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
            title={projectId}
          >
            {projectId}
          </span>
        )}
        <Link href="/">
          <span className="workspace-btn-ghost" style={{ display: "inline-block", textDecoration: "none" }}>
            Back to site
          </span>
        </Link>
      </div>
    </header>
  );
}
