import { Link } from "wouter";
import {
  Activity,
  ChevronLeft,
  FolderOpen,
  LayoutGrid,
  Settings,
} from "lucide-react";
import type { ProviderHealthPayload } from "../../lib/api";

type Props = {
  open: boolean;
  onToggle: () => void;
  providerHealth: ProviderHealthPayload | null;
  showFieldsEditor: boolean;
  onToggleFieldsEditor: () => void;
  onClearSession: () => void;
};

function NavItem({
  icon: Icon,
  label,
  active,
  onClick,
}: {
  icon: typeof LayoutGrid;
  label: string;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        width: "100%",
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "9px 12px",
        borderRadius: 8,
        border: "none",
        cursor: onClick ? "pointer" : "default",
        background: active ? "var(--ws-accent-muted)" : "transparent",
        color: active ? "var(--ws-text)" : "var(--ws-text-muted)",
        fontSize: 13,
        fontWeight: 500,
        textAlign: "left",
        fontFamily: "inherit",
      }}
    >
      <Icon size={16} strokeWidth={1.75} />
      {label}
    </button>
  );
}

export function WorkspaceSidebar({
  open,
  onToggle,
  providerHealth,
  showFieldsEditor,
  onToggleFieldsEditor,
  onClearSession,
}: Props) {
  if (!open) {
    return (
      <button
        type="button"
        onClick={onToggle}
        aria-label="Open sidebar"
        style={{
          position: "fixed",
          left: 12,
          top: 12,
          zIndex: 30,
          padding: 8,
          background: "var(--ws-surface)",
          border: "1px solid var(--ws-border)",
          borderRadius: 8,
          color: "var(--ws-text-muted)",
          cursor: "pointer",
        }}
      >
        <LayoutGrid size={18} />
      </button>
    );
  }

  const readyCount = Object.values(providerHealth?.providers || {}).filter((p) => p?.ready).length;
  const totalCount = Object.keys(providerHealth?.providers || {}).length;

  return (
    <aside className="workspace-sidebar" style={{ width: 260 }}>
      <div
        style={{
          padding: "16px 18px",
          borderBottom: "1px solid var(--ws-border)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <Link href="/">
          <span style={{ fontSize: 14, fontWeight: 600, letterSpacing: "-0.02em", color: "var(--ws-text)" }}>
            AI Editor
          </span>
        </Link>
        <button
          type="button"
          onClick={onToggle}
          className="workspace-btn-ghost"
          style={{ padding: 6 }}
          aria-label="Collapse sidebar"
        >
          <ChevronLeft size={16} />
        </button>
      </div>

      <nav style={{ flex: 1, padding: 12, display: "flex", flexDirection: "column", gap: 4 }}>
        <NavItem icon={LayoutGrid} label="Current session" active />
        <NavItem
          icon={FolderOpen}
          label="Project fields"
          active={showFieldsEditor}
          onClick={onToggleFieldsEditor}
        />
        <NavItem icon={Activity} label="Render status" />
        <NavItem icon={Settings} label="Clear session" onClick={onClearSession} />
      </nav>

      <div style={{ padding: 14, borderTop: "1px solid var(--ws-border)" }}>
        <div className="workspace-card" style={{ padding: 12 }}>
          <p className="workspace-section-label" style={{ marginBottom: 6 }}>
            System
          </p>
          <p style={{ fontSize: 12, color: "var(--ws-text-muted)", margin: 0, lineHeight: 1.5 }}>
            {providerHealth?.ready
              ? "All required providers are ready."
              : totalCount > 0
                ? `${readyCount}/${totalCount} providers ready.`
                : "Checking provider readiness..."}
          </p>
        </div>
      </div>
    </aside>
  );
}
