import type { ProcessVideoURLPayload } from "../types/pipeline";
import type { PipelineResult } from "../components/VideoPipelinePanel";

export function getApiBase(): string {
  return (import.meta.env.VITE_API_BASE_URL || window.location.origin).replace(/\/$/, "");
}

export type ProviderHealthPayload = {
  success?: boolean;
  ready?: boolean;
  providers?: Record<
    string,
    {
      name?: string;
      required?: boolean;
      configured?: boolean;
      ready?: boolean;
      code?: string;
      message?: string;
    }
  >;
};

export type DriveStatus = {
  connected: boolean;
  email?: string | null;
  error?: string;
};

export async function fetchProviderHealth(apiBase: string): Promise<ProviderHealthPayload> {
  const response = await fetch(`${apiBase}/health/providers`);
  if (!response.ok) {
    throw new Error(`Provider health request failed with ${response.status}`);
  }
  return response.json();
}

export async function fetchDriveStatus(apiBase: string): Promise<DriveStatus> {
  const response = await fetch(`${apiBase}/google-drive/oauth/status`);
  return response.json();
}

export async function startDriveOAuth(apiBase: string): Promise<string> {
  const response = await fetch(`${apiBase}/google-drive/oauth/start`, { method: "GET" });
  const data = await response.json();
  if (!response.ok || data.success === false) {
    throw new Error(data.error || "Failed to start Google Drive OAuth.");
  }
  if (!data.auth_url) {
    throw new Error("No Google OAuth URL was returned by backend.");
  }
  return data.auth_url as string;
}

export async function fetchJobStatus(
  apiBase: string,
  projectId: string
): Promise<PipelineResult> {
  const response = await fetch(`${apiBase}/jobs/${projectId}/status`);
  if (!response.ok) {
    throw new Error(`Status polling failed with ${response.status}`);
  }
  return response.json();
}

export async function submitPipelinePayload(
  apiBase: string,
  payload: ProcessVideoURLPayload
): Promise<PipelineResult> {
  const response = await fetch(`${apiBase}/process-video-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return response.json();
}

export function isTerminalJobCategory(category?: string): boolean {
  return (
    category === "complete" ||
    category === "failed" ||
    category === "blocked" ||
    category === "waiting_for_user_input"
  );
}
