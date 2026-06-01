import { useCallback, useEffect, useState } from "react";
import type { PipelineResult } from "../VideoPipelinePanel";
import { StatusRail } from "../StatusRail";
import { ResultPreviewCard } from "../ResultPreviewCard";
import { WorkspaceProviderCard } from "./WorkspaceProviderCard";
import {
  fetchDriveStatus,
  fetchProviderHealth,
  startDriveOAuth,
  type DriveStatus,
  type ProviderHealthPayload,
} from "../../lib/api";

type Props = {
  apiBase: string;
  result: PipelineResult | null;
  isPolling: boolean;
};

export function WorkspaceStatusPanel({ apiBase, result, isPolling }: Props) {
  const [providerHealth, setProviderHealth] = useState<ProviderHealthPayload | null>(null);
  const [driveStatus, setDriveStatus] = useState<DriveStatus | null>(null);
  const [isHealthLoading, setIsHealthLoading] = useState(false);
  const [isDriveLoading, setIsDriveLoading] = useState(false);

  const loadHealth = useCallback(async () => {
    setIsHealthLoading(true);
    try {
      setProviderHealth(await fetchProviderHealth(apiBase));
    } catch {
      setProviderHealth({ success: false, ready: false, providers: {} });
    } finally {
      setIsHealthLoading(false);
    }
  }, [apiBase]);

  const loadDrive = useCallback(async () => {
    setIsDriveLoading(true);
    try {
      setDriveStatus(await fetchDriveStatus(apiBase));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Unable to check Drive.";
      setDriveStatus({ connected: false, error: message });
    } finally {
      setIsDriveLoading(false);
    }
  }, [apiBase]);

  const handleConnectDrive = useCallback(async () => {
    setIsDriveLoading(true);
    try {
      const authUrl = await startDriveOAuth(apiBase);
      const popup = window.open(authUrl, "_blank", "width=520,height=720");
      if (!popup) {
        throw new Error("Popup blocked. Allow popups and try again.");
      }
      for (let i = 0; i < 45; i += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 2000));
        const status = await fetchDriveStatus(apiBase);
        setDriveStatus(status);
        if (status.connected) return;
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "OAuth failed.";
      setDriveStatus({ connected: false, error: message });
    } finally {
      setIsDriveLoading(false);
    }
  }, [apiBase]);

  useEffect(() => {
    void loadHealth();
    void loadDrive();
  }, [loadDrive, loadHealth]);

  const readyProviders = Object.values(providerHealth?.providers || {}).filter((p) => p?.ready).length;
  const totalProviders = Object.keys(providerHealth?.providers || {}).length;

  return (
    <>
      <section>
        <h3 className="workspace-section-label">Pipeline</h3>
        <StatusRail result={result} isPolling={isPolling} />
      </section>

      <section>
        <h3 className="workspace-section-label">Infrastructure</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <WorkspaceProviderCard
            title="Provider health"
            description="Model, render, and storage readiness."
            status={
              isHealthLoading
                ? "connecting"
                : providerHealth?.ready
                  ? "connected"
                  : providerHealth
                    ? "error"
                    : "disconnected"
            }
            detail={
              totalProviders > 0
                ? `${readyProviders}/${totalProviders} providers ready`
                : "Run a health check to verify configuration."
            }
            onAction={() => void loadHealth()}
            isLoading={isHealthLoading}
          />
          <WorkspaceProviderCard
            title="Google Drive"
            description="OAuth connection for folder-based sources."
            status={
              isDriveLoading
                ? "connecting"
                : driveStatus?.connected
                  ? "connected"
                  : driveStatus?.error
                    ? "error"
                    : "disconnected"
            }
            detail={
              driveStatus?.connected
                ? driveStatus.email || "Connected"
                : driveStatus?.error || "Not connected"
            }
            onAction={() => void (driveStatus?.connected ? loadDrive() : handleConnectDrive())}
            actionLabel={driveStatus?.connected ? "Refresh" : "Connect"}
            isLoading={isDriveLoading}
          />
        </div>
      </section>

      {result?.success && (result.preview_url || result.url) && (
        <section>
          <h3 className="workspace-section-label">Preview</h3>
          <ResultPreviewCard result={result} apiBase={apiBase} />
        </section>
      )}
    </>
  );
}
