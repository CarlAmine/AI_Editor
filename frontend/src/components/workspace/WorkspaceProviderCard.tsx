import { AlertCircle, CheckCircle2, Loader2, RefreshCw } from "lucide-react";

type ProviderStatus = "connected" | "connecting" | "disconnected" | "error";

type Props = {
  title: string;
  description: string;
  status: ProviderStatus;
  detail?: string | null;
  onAction?: () => void;
  actionLabel?: string;
  isLoading?: boolean;
};

function StatusIcon({ status }: { status: ProviderStatus }) {
  switch (status) {
    case "connected":
      return <CheckCircle2 size={16} style={{ color: "var(--ws-success)" }} />;
    case "error":
      return <AlertCircle size={16} style={{ color: "var(--ws-danger)" }} />;
    case "connecting":
      return <Loader2 size={16} className="animate-spin" style={{ color: "var(--ws-text-muted)" }} />;
    default:
      return <AlertCircle size={16} style={{ color: "var(--ws-text-subtle)" }} />;
  }
}

function statusLabel(status: ProviderStatus): string {
  switch (status) {
    case "connected":
      return "Connected";
    case "connecting":
      return "Checking";
    case "error":
      return "Issue";
    default:
      return "Disconnected";
  }
}

export function WorkspaceProviderCard({
  title,
  description,
  status,
  detail,
  onAction,
  actionLabel = "Refresh",
  isLoading,
}: Props) {
  return (
    <div className="workspace-card">
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 8 }}>
        <div>
          <p style={{ margin: 0, fontSize: 13, fontWeight: 600 }}>{title}</p>
          <p style={{ margin: "4px 0 0", fontSize: 12, color: "var(--ws-text-muted)" }}>{description}</p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--ws-text-muted)" }}>
          <StatusIcon status={status} />
          {statusLabel(status)}
        </div>
      </div>
      {detail && (
        <p style={{ margin: "0 0 10px", fontSize: 12, color: "var(--ws-text-muted)", lineHeight: 1.45 }}>
          {detail}
        </p>
      )}
      {onAction && (
        <button type="button" className="workspace-btn-ghost" onClick={onAction} disabled={isLoading}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            {isLoading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
            {actionLabel}
          </span>
        </button>
      )}
    </div>
  );
}
