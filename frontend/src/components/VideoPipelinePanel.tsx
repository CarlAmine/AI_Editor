import React, { useState, FormEvent } from "react";
import {
  Film,
  ArrowUp,
  ArrowDown,
  Trash2,
  Plus,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { PipelineProgress, PipelineStage } from "./PipelineProgress";
import { YouTubePublishStep } from "./YouTubePublishStep";

type Props = {
  apiBase: string;
  onAnalyzerSummary?: (summary: string) => void;
  currentState?: Record<string, unknown>;
};

type VideoSegment = {
  start: number;
  end: number;
};

type VideoSource = {
  label: number;
  url: string;
  segments?: VideoSegment[];
};

type PipelineResult = {
  success?: boolean;
  url?: string;
  preview_url?: string;
  preview_mode?: string;
  intent_mode?: string;
  project_id?: string;
  user_notice?: string;
  status?: string;
  error?: string;
  render_id?: string;
};

/** Intelligently truncate a URL: show domain + last path segment */
function smartTruncateUrl(url: string, maxLen = 60): string {
  try {
    const parsed = new URL(url);
    const domain = parsed.hostname.replace(/^www\./, "");
    const pathParts = parsed.pathname.split("/").filter(Boolean);
    const lastPart = pathParts[pathParts.length - 1] || "";
    const candidate =
      pathParts.length > 1
        ? `${domain}/\u2026/${lastPart}`
        : `${domain}/${lastPart}`;
    return candidate.length > maxLen
      ? candidate.substring(0, maxLen) + "\u2026"
      : candidate;
  } catch {
    return url.length > maxLen ? url.substring(0, maxLen) + "\u2026" : url;
  }
}

export const VideoPipelinePanel: React.FC<Props> = ({
  apiBase,
  onAnalyzerSummary,
  currentState = {},
}) => {
  const normalizeSourceUrl = (value: string): string => value.trim().toLowerCase();
  const toAbsoluteUrl = (value?: string | null): string => {
    if (!value) return "";
    if (value.startsWith("/")) return `${apiBase}${value}`;
    return value;
  };
  const getPreviewUrl = (value?: string | null): string => toAbsoluteUrl(value);

  const [primaryUrl, setPrimaryUrl] = useState("");
  const [sources, setSources] = useState<VideoSource[]>([]);
  const [newSourceUrl, setNewSourceUrl] = useState("");
  const [newSourceSegments, setNewSourceSegments] = useState<string>("");
  const [googleDriveLink, setGoogleDriveLink] = useState("");
  const [prompt, setPrompt] = useState("");
  const [musicMode, setMusicMode] = useState<"original" | "custom">("original");
  const [customMusicUrl, setCustomMusicUrl] = useState("");
  const [customMusicSegment, setCustomMusicSegment] = useState("");
  const [intentMode, setIntentMode] = useState<"video" | "shorts">("video");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorDismissed, setErrorDismissed] = useState(false);
  const [bulkSourceSpec, setBulkSourceSpec] = useState("");
  const [isConnectingDriveOauth, setIsConnectingDriveOauth] = useState(false);
  const [driveOauthEmail, setDriveOauthEmail] = useState<string | null>(null);
  const [driveOauthMessage, setDriveOauthMessage] = useState<string | null>(null);

  // Progress tracking
  const [currentStage, setCurrentStage] = useState<PipelineStage | null>(null);
  const [stageFailed, setStageFailed] = useState(false);

  const handleAddSource = () => {
    if (!newSourceUrl.trim()) {
      setError("Please enter a video URL.");
      setErrorDismissed(false);
      return;
    }
    const segments: VideoSegment[] = [];
    if (newSourceSegments.trim()) {
      const parts = newSourceSegments.split(",");
      for (const part of parts) {
        const [startStr, endStr] = part.trim().split("-");
        if (startStr && endStr) {
          const start = parseFloat(startStr);
          const end = parseFloat(endStr);
          if (!isNaN(start) && !isNaN(end) && start < end) {
            segments.push({ start, end });
          }
        }
      }
    }
    const newLabel = sources.length + 1;
    setSources([
      ...sources,
      {
        label: newLabel,
        url: newSourceUrl.trim(),
        segments: segments.length > 0 ? segments : undefined,
      },
    ]);
    setNewSourceUrl("");
    setNewSourceSegments("");
    setError(null);
  };

  const handleRemoveSource = (index: number) => {
    setSources((prev) => {
      const updated = prev.filter((_, i) => i !== index);
      return updated.map((src, i) => ({ ...src, label: i + 1 }));
    });
  };

  const handleMoveSourceUp = (index: number) => {
    if (index === 0) return;
    const updated = [...sources];
    [updated[index - 1], updated[index]] = [updated[index], updated[index - 1]];
    setSources(updated.map((src, i) => ({ ...src, label: i + 1 })));
  };

  const handleMoveSourceDown = (index: number) => {
    if (index === sources.length - 1) return;
    const updated = [...sources];
    [updated[index], updated[index + 1]] = [updated[index + 1], updated[index]];
    setSources(updated.map((src, i) => ({ ...src, label: i + 1 })));
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setErrorDismissed(false);
    setResult(null);
    setStageFailed(false);

    const parsedBulkSources = parseBulkSources(bulkSourceSpec);
    const bulkUrlsWithSegments = new Set(
      parsedBulkSources
        .filter((source) => (source.segments?.length || 0) > 0)
        .map((source) => normalizeSourceUrl(source.url))
    );
    const filteredManualSources = sources.filter((source) => {
      const hasSegments = (source.segments?.length || 0) > 0;
      if (hasSegments) return true;
      return !bulkUrlsWithSegments.has(normalizeSourceUrl(source.url));
    });
    const combinedSources = [
      ...filteredManualSources,
      ...parsedBulkSources.map((s, idx) => ({
        ...s,
        label: filteredManualSources.length + idx + 1,
      })),
    ];

    if (!primaryUrl.trim()) {
      setError("Please provide the primary video URL for analysis.");
      return;
    }
    if (combinedSources.length === 0 && !googleDriveLink.trim()) {
      setError("Please add at least one source video or provide a Google Drive folder link.");
      return;
    }
    if (!prompt.trim()) {
      setError("Please provide an editing description.");
      return;
    }
    if (musicMode === "custom" && !customMusicUrl.trim()) {
      setError("Please provide a custom music URL or select 'Use original audio'.");
      return;
    }

    const payload = {
      primary_url: primaryUrl.trim(),
      sources: combinedSources,
      prompt: prompt.trim(),
      music_mode: musicMode,
      custom_music_url: musicMode === "custom" ? customMusicUrl.trim() : null,
      custom_music_segment:
        musicMode === "custom" && customMusicSegment.trim()
          ? customMusicSegment.trim()
          : null,
      google_drive_link: googleDriveLink.trim() || null,
      requirements_state: {
        ...(currentState || {}),
        intent_mode: intentMode,
      },
    };

    setIsSubmitting(true);
    setCurrentStage("analyzing");

    const stageTimer1 = setTimeout(() => setCurrentStage("editing"), 8000);
    const stageTimer2 = setTimeout(() => setCurrentStage("rendering"), 20000);

    try {
      const response = await fetch(`${apiBase}/process-video-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      clearTimeout(stageTimer1);
      clearTimeout(stageTimer2);

      const data: PipelineResult = await response.json();

      if (!response.ok || data.success === false) {
        setStageFailed(true);
        setError(data.error || "The pipeline failed. Check server logs.");
        setResult(data);
      } else {
        setCurrentStage("done");
        setResult(data);
        if (onAnalyzerSummary) {
          onAnalyzerSummary(
            `Processed ${sources.length} video(s) with brief: ${prompt}`
          );
        }
      }
    } catch (err: unknown) {
      clearTimeout(stageTimer1);
      clearTimeout(stageTimer2);
      setStageFailed(true);
      const message =
        err instanceof Error
          ? err.message
          : "Network error while calling /process-video-url.";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleConnectDriveOauth = async () => {
    setIsConnectingDriveOauth(true);
    setDriveOauthMessage(null);
    try {
      const response = await fetch(`${apiBase}/google-drive/oauth/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      const data = await response.json();
      if (data.auth_url) {
        window.open(data.auth_url, "_blank");
        setDriveOauthMessage("OAuth window opened. Complete authorization then click 'Check Status'.");
      } else {
        setDriveOauthMessage(data.message || "OAuth start failed.");
      }
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Error starting Google Drive OAuth.";
      setDriveOauthMessage(message);
    } finally {
      setIsConnectingDriveOauth(false);
    }
  };

  const handleCheckDriveOauthStatus = async () => {
    try {
      const response = await fetch(`${apiBase}/google-drive/oauth/status`);
      const data = await response.json();
      setDriveOauthEmail(data.email || null);
      setDriveOauthMessage(
        data.connected
          ? `Connected as: ${data.email}`
          : "Not connected. Please authorize Google Drive."
      );
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Error checking Google Drive OAuth status.";
      setDriveOauthMessage(message);
    }
  };

  const parseBulkSources = (input: string): VideoSource[] => {
    const lines = input
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    const parsed: VideoSource[] = [];

    const toSeconds = (value: string): number | null => {
      const parts = value.split(":").map((num) => parseFloat(num));
      if (parts.some((p) => Number.isNaN(p))) return null;
      if (parts.length === 1) return parts[0];
      if (parts.length === 2) return parts[0] * 60 + parts[1];
      if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
      return null;
    };

    for (const line of lines) {
      const separatorIndex = line.indexOf(" - ");
      const url = separatorIndex === -1 ? line : line.slice(0, separatorIndex);
      const segmentsPart = separatorIndex === -1 ? "" : line.slice(separatorIndex + 3);
      const cleanedUrl = url.trim();
      if (!cleanedUrl) continue;
      const segments: VideoSegment[] = [];
      if (segmentsPart) {
        const segmentParts = segmentsPart.split(",");
        for (const seg of segmentParts) {
          const [startRaw, endRaw] = seg.trim().split("-");
          if (!startRaw || !endRaw) continue;
          const start = toSeconds(startRaw.trim());
          const end = toSeconds(endRaw.trim());
          if (start !== null && end !== null && start < end) {
            segments.push({ start, end });
          }
        }
      }
      parsed.push({
        label: parsed.length + 1,
        url: cleanedUrl,
        segments: segments.length > 0 ? segments : undefined,
      });
    }
    return parsed;
  };

  return (
    <section className="panel">
      <header className="panel-header">
        <h2 className="panel-title">Build Your Edit</h2>
        <p className="panel-caption">
          Add the reference video, define source footage, and render a polished
          edit from one workspace.
        </p>
      </header>

      <form className="panel-form" onSubmit={handleSubmit}>
        {/* Reference Video URL — prominent */}
        <label className="field field--prominent">
          <span className="field-label field-label--prominent">
            Reference Video URL
          </span>
          <input
            type="text"
            className="field-input field-input--prominent"
            placeholder="https://www.youtube.com/watch?v=... or https://www.tiktok.com/@.../video/..."
            value={primaryUrl}
            onChange={(e) => {
              setPrimaryUrl(e.target.value);
              setError(null);
            }}
          />
        </label>

        {/* Source Footage — collapsible, open by default */}
        <details className="collapsible-section" open>
          <summary className="collapsible-summary">
            <span className="collapsible-title">Source Footage</span>
            <ChevronDown className="collapsible-chevron collapsible-chevron--open" size={16} />
            <ChevronUp className="collapsible-chevron collapsible-chevron--closed" size={16} />
          </summary>
          <div className="collapsible-body">
            <div className="field">
              <span className="field-label">Add a Single Source</span>
              <div className="field-group">
                <input
                  type="text"
                  className="field-input"
                  placeholder="Source video URL"
                  value={newSourceUrl}
                  onChange={(e) => setNewSourceUrl(e.target.value)}
                />
                <input
                  type="text"
                  className="field-input"
                  placeholder="Segments e.g. 10-20, 30-45"
                  value={newSourceSegments}
                  onChange={(e) => setNewSourceSegments(e.target.value)}
                />
                <button
                  type="button"
                  onClick={handleAddSource}
                  className="btn btn-secondary"
                >
                  <Plus size={15} />
                  Add
                </button>
              </div>
              <p className="field-hint">
                Leave segments empty to use the entire source. Use{" "}
                <code>start-end</code> in seconds, separated by commas.
              </p>
            </div>

            {sources.length > 0 && (
              <div className="sources-list">
                <p className="field-label">Ordered Sources</p>
                {sources.map((source, idx) => (
                  <div key={idx} className="source-item">
                    <div className="source-thumbnail" aria-hidden="true" />
                    <div className="source-info">
                      <span className="source-label">{source.label}</span>
                      <div className="source-details">
                        <a
                          href={source.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="source-url"
                          title={source.url}
                        >
                          {smartTruncateUrl(source.url)}
                        </a>
                        {source.segments && source.segments.length > 0 && (
                          <span className="source-segments">
                            {source.segments.length} segment(s):{" "}
                            {source.segments
                              .map((s) => `${s.start}s\u2013${s.end}s`)
                              .join(", ")}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="source-controls">
                      <button
                        type="button"
                        onClick={() => handleMoveSourceUp(idx)}
                        disabled={idx === 0}
                        className="btn btn-mini"
                        title="Move up"
                      >
                        <ArrowUp size={13} />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleMoveSourceDown(idx)}
                        disabled={idx === sources.length - 1}
                        className="btn btn-mini"
                        title="Move down"
                      >
                        <ArrowDown size={13} />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleRemoveSource(idx)}
                        className="btn btn-mini btn-danger"
                        title="Remove"
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="section-divider" />

            <label className="field">
              <span className="field-label">
                Bulk Source Import{" "}
                <span className="field-label-optional">(optional)</span>
              </span>
              <textarea
                className="field-input field-textarea"
                placeholder={"One URL per line. Optionally add segments:\nhttps://... - 10-20, 30-45\nhttps://..."}
                value={bulkSourceSpec}
                onChange={(e) => setBulkSourceSpec(e.target.value)}
                rows={3}
              />
              <p className="field-hint">
                Format: <code>URL - start-end, start-end</code>. Segments are in
                seconds or <code>HH:MM:SS</code>.
              </p>
            </label>
          </div>
        </details>

        {/* Google Drive — collapsible, closed by default */}
        <details className="collapsible-section">
          <summary className="collapsible-summary">
            <span className="collapsible-title">Google Drive</span>
            <ChevronDown className="collapsible-chevron collapsible-chevron--open" size={16} />
            <ChevronUp className="collapsible-chevron collapsible-chevron--closed" size={16} />
          </summary>
          <div className="collapsible-body">
            <div className="field">
              <span className="field-label">Connect Google Account</span>
              <div className="field-group">
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={isConnectingDriveOauth}
                  onClick={handleConnectDriveOauth}
                >
                  {isConnectingDriveOauth ? "Connecting\u2026" : "Connect Google Drive"}
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={handleCheckDriveOauthStatus}
                >
                  Check Status
                </button>
              </div>
              <p className="field-hint">
                Connect your Google account to load source files from Drive.
              </p>
              {driveOauthMessage && (
                <p className="field-hint">
                  {driveOauthMessage}
                  {driveOauthEmail ? ` Connected as: ${driveOauthEmail}` : ""}
                </p>
              )}
            </div>

            <label className="field">
              <span className="field-label">
                Google Drive Folder Link{" "}
                <span className="field-label-optional">(optional)</span>
              </span>
              <input
                type="text"
                className="field-input"
                placeholder="https://drive.google.com/drive/folders/..."
                value={googleDriveLink}
                onChange={(e) => {
                  setGoogleDriveLink(e.target.value);
                  setError(null);
                }}
              />
              <p className="field-hint">
                Optional alternative to source URLs. Source videos will be loaded
                from this folder.
              </p>
            </label>
          </div>
        </details>

        {/* Audio Settings — collapsible, closed by default */}
        <details className="collapsible-section">
          <summary className="collapsible-summary">
            <span className="collapsible-title">Audio Settings</span>
            <ChevronDown className="collapsible-chevron collapsible-chevron--open" size={16} />
            <ChevronUp className="collapsible-chevron collapsible-chevron--closed" size={16} />
          </summary>
          <div className="collapsible-body">
            <label className="field">
              <span className="field-label">Audio / Music</span>
              <div className="select-wrapper">
                <select
                  className="field-input field-select"
                  value={musicMode}
                  onChange={(e) => {
                    setMusicMode(e.target.value as "original" | "custom");
                    setError(null);
                  }}
                >
                  <option value="original">Use original audio from clips</option>
                  <option value="custom">Use custom music from URL</option>
                </select>
              </div>
            </label>

            {musicMode === "custom" && (
              <>
                <label className="field">
                  <span className="field-label">Custom Music URL</span>
                  <input
                    type="text"
                    className="field-input"
                    placeholder="https://www.youtube.com/watch?v=... (audio or music video)"
                    value={customMusicUrl}
                    onChange={(e) => setCustomMusicUrl(e.target.value)}
                  />
                </label>
                <label className="field">
                  <span className="field-label">
                    Custom Music Segment{" "}
                    <span className="field-label-optional">(optional)</span>
                  </span>
                  <input
                    type="text"
                    className="field-input"
                    placeholder="0:00-0:13 or 10-25"
                    value={customMusicSegment}
                    onChange={(e) => setCustomMusicSegment(e.target.value)}
                  />
                  <p className="field-hint">
                    If provided, only this portion of the music URL is used.
                    Accepts seconds or <code>HH:MM:SS</code> ranges.
                  </p>
                </label>
              </>
            )}
          </div>
        </details>

        {/* Edit Brief — prominent */}
        <label className="field field--prominent">
          <span className="field-label field-label--prominent">Edit Brief</span>
          <textarea
            className="field-input field-input--prominent field-textarea"
            placeholder="e.g. Create a 30s vertical highlight reel with upbeat pacing and bold captions."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={4}
          />
        </label>

        <label className="field">
          <span className="field-label">Output Intent</span>
          <div className="select-wrapper">
            <select
              className="field-input field-select"
              value={intentMode}
              onChange={(e) => setIntentMode(e.target.value as "video" | "shorts")}
            >
              <option value="video">Video (Standard)</option>
              <option value="shorts">Shorts (9:16 preview from 16:9 master)</option>
            </select>
          </div>
        </label>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={isSubmitting}
          className="btn btn-primary btn-large btn-render"
        >
          {isSubmitting ? (
            <>
              <span className="btn-spinner" />
              {currentStage === "analyzing"
                ? "Analyzing\u2026"
                : currentStage === "editing"
                ? "Editing\u2026"
                : currentStage === "rendering"
                ? "Rendering\u2026"
                : "Processing\u2026"}
            </>
          ) : (
            <>
              <Film size={20} />
              Render Video
            </>
          )}
        </button>
      </form>

      {/* Progress Indicator */}
      <PipelineProgress currentStage={currentStage} failed={stageFailed} />

      {/* Error Display */}
      {error && !errorDismissed && (
        <div className="alert alert-error">
          <span>{error}</span>
          <button
            type="button"
            className="alert-dismiss"
            onClick={() => setErrorDismissed(true)}
            aria-label="Dismiss"
          >
            &times;
          </button>
        </div>
      )}

      {/* Success alert */}
      {result?.success && (
        <div className="alert alert-success">
          <strong>Success:</strong> Your video is ready.{" "}
          {(getPreviewUrl(result.preview_url) || result.url) && (
            <a
              href={getPreviewUrl(result.preview_url) || result.url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Open video
            </a>
          )}
        </div>
      )}

      {result?.user_notice && (
        <div className="alert alert-error">
          <strong>Notice:</strong> {result.user_notice}
        </div>
      )}
    </section>
  );
};
