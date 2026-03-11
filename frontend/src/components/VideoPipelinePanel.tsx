import React, { useState, FormEvent } from "react";

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

type YouTubeUploadResult = {
  success?: boolean;
  error?: string;
  video_id?: string;
  youtube_url?: string;
  title?: string;
};

export const VideoPipelinePanel: React.FC<Props> = ({
  apiBase,
  onAnalyzerSummary,
  currentState = {},
}) => {
  const normalizeSourceUrl = (value: string): string => value.trim().toLowerCase();
  const toAbsoluteUrl = (value?: string | null): string => {
    if (!value) return "";
    if (value.startsWith("/")) {
      return `${apiBase}${value}`;
    }
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
  const [isApprovedForYouTube, setIsApprovedForYouTube] = useState(false);
  const [youtubeTitle, setYoutubeTitle] = useState("");
  const [youtubeDescription, setYoutubeDescription] = useState("");
  const [youtubePrivacy, setYoutubePrivacy] = useState<"private" | "public" | "unlisted">("private");
  const [isUploadingYouTube, setIsUploadingYouTube] = useState(false);
  const [youtubeUploadResult, setYoutubeUploadResult] = useState<YouTubeUploadResult | null>(null);
  const [bulkSourceSpec, setBulkSourceSpec] = useState("");
  const [isConnectingDriveOauth, setIsConnectingDriveOauth] = useState(false);
  const [driveOauthEmail, setDriveOauthEmail] = useState<string | null>(null);
  const [driveOauthMessage, setDriveOauthMessage] = useState<string | null>(null);

  // Add a new source to the list
  const handleAddSource = () => {
    if (!newSourceUrl.trim()) {
      setError("Please enter a video URL.");
      return;
    }

    const segments: VideoSegment[] = [];
    if (newSourceSegments.trim()) {
      // Parse segments in format: "10-20, 30-45, 60-75"
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

    // Reset form
    setNewSourceUrl("");
    setNewSourceSegments("");
    setError(null);
  };

  // Remove a source from the list
  const handleRemoveSource = (index: number) => {
    setSources((prev) => {
      const updated = prev.filter((_, i) => i !== index);
      // Renumber labels
      return updated.map((src, i) => ({ ...src, label: i + 1 }));
    });
  };

  // Move source up in the list
  const handleMoveSourceUp = (index: number) => {
    if (index === 0) return;
    const updated = [...sources];
    [updated[index - 1], updated[index]] = [updated[index], updated[index - 1]];
    // Renumber labels
    setSources(
      updated.map((src, i) => ({
        ...src,
        label: i + 1,
      }))
    );
  };

  // Move source down in the list
  const handleMoveSourceDown = (index: number) => {
    if (index === sources.length - 1) return;
    const updated = [...sources];
    [updated[index], updated[index + 1]] = [updated[index + 1], updated[index]];
    // Renumber labels
    setSources(
      updated.map((src, i) => ({
        ...src,
        label: i + 1,
      }))
    );
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setResult(null);
    setYoutubeUploadResult(null);

    const parsedBulkSources = parseBulkSources(bulkSourceSpec);
    const bulkUrlsWithSegments = new Set(
      parsedBulkSources
        .filter((source) => (source.segments?.length || 0) > 0)
        .map((source) => normalizeSourceUrl(source.url))
    );
    const filteredManualSources = sources.filter((source) => {
      const hasSegments = (source.segments?.length || 0) > 0;
      if (hasSegments) {
        return true;
      }
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

    try {
      const response = await fetch(`${apiBase}/process-video-url`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      const data: PipelineResult = await response.json();
      setResult(data);

      if (onAnalyzerSummary) {
        onAnalyzerSummary(
          `Processed ${sources.length} video(s) with brief: ${prompt}`
        );
      }

      if (!response.ok || data.success === false) {
        setError(data.error || "The pipeline failed. Check server logs.");
      } else {
        setIsApprovedForYouTube(false);
        setYoutubeTitle((prompt.trim() || "AI Editor Render").slice(0, 100));
        setYoutubeDescription(prompt.trim());
        setYoutubePrivacy("private");
        // Clear form on success
        setPrimaryUrl("");
        setSources([]);
        setGoogleDriveLink("");
        setPrompt("");
        setMusicMode("original");
        setCustomMusicUrl("");
        setCustomMusicSegment("");
        setIntentMode("video");
        setBulkSourceSpec("");
      }
    } catch (err: any) {
      setError(err?.message || "Network error while calling /process-video-url.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUploadToYouTube = async () => {
    const previewTarget = result?.preview_url || result?.url;
    if (!previewTarget) {
      setError("No render URL available for YouTube upload.");
      return;
    }
    if (!isApprovedForYouTube) {
      setError("Please review and approve the rendered video before uploading.");
      return;
    }
    if (!youtubeTitle.trim()) {
      setError("Please enter a YouTube title.");
      return;
    }

    setError(null);
    setYoutubeUploadResult(null);
    setIsUploadingYouTube(true);

    try {
      const uploadSourceUrl = previewTarget.startsWith("/")
        ? `${apiBase}${previewTarget}`
        : previewTarget;
      const response = await fetch(`${apiBase}/upload-approved-video-youtube`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          render_url: uploadSourceUrl,
          title: youtubeTitle.trim(),
          description: youtubeDescription.trim(),
          privacy_status: youtubePrivacy,
          tags: [],
          category_id: "22",
          made_for_kids: false,
          project_id: result?.project_id || null,
        }),
      });

      const data: YouTubeUploadResult = await response.json();
      setYoutubeUploadResult(data);
      if (!response.ok || data.success === false) {
        setError(data.error || "YouTube upload failed.");
      }
    } catch (err: any) {
      setError(err?.message || "Network error while uploading to YouTube.");
    } finally {
      setIsUploadingYouTube(false);
    }
  };

  const handleConnectDriveOauth = async () => {
    setError(null);
    setDriveOauthMessage(null);
    setDriveOauthEmail(null);
    setIsConnectingDriveOauth(true);
    try {
      const response = await fetch(`${apiBase}/google-drive/oauth/start`, {
        method: "GET",
      });
      const data = await response.json();
      if (!response.ok || data.success === false) {
        setError(data.error || "Failed to start Google Drive OAuth.");
        return;
      }
      if (!data.auth_url) {
        setError("No Google OAuth URL was returned by backend.");
        return;
      }
      const popup = window.open(data.auth_url, "_blank", "width=520,height=720");
      if (!popup) {
        setError("Popup blocked. Please allow popups and try again.");
        return;
      }
      setDriveOauthMessage("Google sign-in opened. Finish login, then connection status will update.");
      for (let i = 0; i < 45; i += 1) {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        const statusRes = await fetch(`${apiBase}/google-drive/oauth/status`);
        const statusData = await statusRes.json();
        if (statusData.connected) {
          setDriveOauthEmail(statusData.email || null);
          setDriveOauthMessage("Google Drive connected successfully.");
          return;
        }
      }
      setDriveOauthMessage("Login not completed yet. You can click 'Check Google Drive Status'.");
    } catch (err: any) {
      setError(err?.message || "Network error while starting Google Drive OAuth.");
    } finally {
      setIsConnectingDriveOauth(false);
    }
  };

  const handleCheckDriveOauthStatus = async () => {
    setError(null);
    try {
      const response = await fetch(`${apiBase}/google-drive/oauth/status`);
      const data = await response.json();
      if (data.connected) {
        setDriveOauthEmail(data.email || null);
        setDriveOauthMessage("Google Drive connected successfully.");
      } else {
        setDriveOauthEmail(null);
        setDriveOauthMessage("Google Drive is not connected yet.");
      }
    } catch (err: any) {
      setError(err?.message || "Network error while checking Google Drive OAuth status.");
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
      if (parts.some((p) => Number.isNaN(p))) {
        return null;
      }
      if (parts.length === 1) {
        return parts[0];
      }
      if (parts.length === 2) {
        return parts[0] * 60 + parts[1];
      }
      if (parts.length === 3) {
        return parts[0] * 3600 + parts[1] * 60 + parts[2];
      }
      return null;
    };

    for (const line of lines) {
      const separatorIndex = line.indexOf(" - ");
      const url = separatorIndex === -1 ? line : line.slice(0, separatorIndex);
      const segmentsPart = separatorIndex === -1 ? "" : line.slice(separatorIndex + 3);
      const cleanedUrl = url.trim();
      if (!cleanedUrl) {
        continue;
      }
      const segments: VideoSegment[] = [];
      if (segmentsPart) {
        const segmentParts = segmentsPart.split(",");
        for (const seg of segmentParts) {
          const [startRaw, endRaw] = seg.trim().split("-");
          if (!startRaw || !endRaw) {
            continue;
          }
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
        <h2 className="panel-title">1. Build Your Edit</h2>
        <p className="panel-caption">
          Add the reference video, define source footage, and render a polished
          edit from one workspace.
        </p>
      </header>

      <form className="panel-form" onSubmit={handleSubmit}>
        {/* Primary URL for analysis */}
        <label className="field">
          <span className="field-label">
            Reference Video URL
          </span>
          <input
            type="text"
            className="field-input"
            placeholder="https://www.youtube.com/watch?v=... or https://www.tiktok.com/@.../video/..."
            value={primaryUrl}
            onChange={(e) => {
              setPrimaryUrl(e.target.value);
              setError(null);
            }}
          />
        </label>

        {/* Source Videos Section */}
        <fieldset className="field-fieldset">
          <legend className="field-legend">Source Footage</legend>

          {/* Add new source */}
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
                placeholder="Segments (for example: 10-20, 30-45)"
                value={newSourceSegments}
                onChange={(e) => setNewSourceSegments(e.target.value)}
              />
              <button
                type="button"
                onClick={handleAddSource}
                className="button button-secondary"
              >
                Add
              </button>
            </div>
            <p className="field-hint">
              Leave segments empty to use the entire source. Use `start-end` in
              seconds, separated by commas.
            </p>
          </div>

          {/* List of sources */}
          {sources.length > 0 && (
            <div className="sources-list">
              <p className="field-label">Ordered Sources</p>
              {sources.map((source, idx) => (
                <div key={idx} className="source-item">
                  <div className="source-info">
                    <span className="source-label">{source.label}</span>
                    <div className="source-details">
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="source-url"
                      >
                        {source.url.substring(0, 50)}...
                      </a>
                      {source.segments && source.segments.length > 0 && (
                        <span className="source-segments">
                          {source.segments.length} segment(s):{" "}
                          {source.segments
                            .map((s) => `${s.start}s-${s.end}s`)
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
                      className="button button-mini"
                      title="Move up"
                    >
                      Up
                    </button>
                    <button
                      type="button"
                      onClick={() => handleMoveSourceDown(idx)}
                      disabled={idx === sources.length - 1}
                      className="button button-mini"
                      title="Move down"
                    >
                      Down
                    </button>
                    <button
                      type="button"
                      onClick={() => handleRemoveSource(idx)}
                      className="button button-mini button-danger"
                      title="Remove"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </fieldset>

        <label className="field">
          <span className="field-label">Bulk Source Import</span>
          <textarea
            className="field-input field-textarea"
            placeholder={`https://www.youtube.com/watch?v=abcDEF - 10-20, 35-45\nhttps://youtu.be/xyz123 - 0:15-0:45`}
            rows={4}
            value={bulkSourceSpec}
            onChange={(e) => setBulkSourceSpec(e.target.value)}
          />
          <p className="field-hint">
            One source per line. Format: <code>URL - start-end, start-end</code>.
            Timestamps can be in seconds or <code>HH:MM:SS</code>.
          </p>
        </label>

        <label className="field">
          <span className="field-label">Google Drive Connection</span>
          <div className="field-group">
            <button
              type="button"
              className="button button-secondary"
              disabled={isConnectingDriveOauth}
              onClick={handleConnectDriveOauth}
            >
              {isConnectingDriveOauth ? "Connecting..." : "Connect Google Drive"}
            </button>
            <button
              type="button"
              className="button button-secondary"
              onClick={handleCheckDriveOauthStatus}
            >
              Check Google Drive Status
            </button>
          </div>
          <p className="field-hint">
            Connect your Google account if you want to load source files from Drive.
          </p>
          {driveOauthMessage && (
            <p className="field-hint">
              {driveOauthMessage}
              {driveOauthEmail ? ` Connected as: ${driveOauthEmail}` : ""}
            </p>
          )}
        </label>

        <label className="field">
          <span className="field-label">Google Drive Folder Link (Optional)</span>
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
            Optional alternative to source URLs. If provided, source videos will
            be loaded from this folder.
          </p>
        </label>

        {/* Edit Brief */}
        <label className="field">
          <span className="field-label">Edit Brief</span>
          <textarea
            className="field-input field-textarea"
            placeholder="e.g. Create a 30s vertical highlight reel with upbeat pacing and bold captions."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={4}
          />
        </label>

        <label className="field">
          <span className="field-label">Output Intent</span>
          <select
            className="field-input"
            value={intentMode}
            onChange={(e) => setIntentMode(e.target.value as "video" | "shorts")}
          >
            <option value="video">Video (Standard)</option>
            <option value="shorts">Shorts (9:16 preview from 16:9 master)</option>
          </select>
        </label>

        {/* Music Mode */}
        <label className="field">
          <span className="field-label">Audio/Music</span>
          <select
            className="field-input"
            value={musicMode}
            onChange={(e) => {
              setMusicMode(e.target.value as "original" | "custom");
              setError(null);
            }}
          >
            <option value="original">Use original audio from clips</option>
            <option value="custom">Use custom music from URL</option>
          </select>
        </label>

        {/* Custom Music URL (conditional) */}
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
              <span className="field-label">Custom Music Segment (Optional)</span>
              <input
                type="text"
                className="field-input"
                placeholder="0:00-0:13 or 10-25"
                value={customMusicSegment}
                onChange={(e) => setCustomMusicSegment(e.target.value)}
              />
              <p className="field-hint">
                If provided, only this portion of the music URL is used. Accepts
                seconds or <code>HH:MM:SS</code> ranges.
              </p>
            </label>
          </>
        )}

        {/* Submit Button */}
        <button
          type="submit"
          disabled={isSubmitting}
          className="button button-primary button-large"
        >
          {isSubmitting ? "Rendering..." : "Render Video"}
        </button>
      </form>

      {/* Error Display */}
      {error && <div className="alert alert-error">{error}</div>}

      {/* Result Display */}
      {result && (
        <div className={`alert ${result.success ? "alert-success" : "alert-error"}`}>
          {result.success ? (
            <>
              <strong>Success:</strong> Your video is ready:{" "}
              <a
                href={getPreviewUrl(result.preview_url) || result.url}
                target="_blank"
                rel="noopener noreferrer"
              >
                {getPreviewUrl(result.preview_url) || result.url}
              </a>
              {getPreviewUrl(result.preview_url) || result.url ? (
                <div className="render-preview">
                  <video
                    className="render-preview-video"
                    src={getPreviewUrl(result.preview_url) || result.url}
                    controls
                    preload="metadata"
                  />
                </div>
              ) : null}
            </>
          ) : (
            <>
              <strong>Error:</strong> {result.error}
            </>
          )}
        </div>
      )}

      {result?.user_notice && (
        <div className="alert alert-error">
          <strong>Notice:</strong> {result.user_notice}
        </div>
      )}

      {result?.success && (result.preview_url || result.url) && (
        <div className="youtube-upload-card">
          <h3 className="panel-title">2. Review and Upload</h3>
          <p className="field-hint">
            Review the rendered video, then approve it before sending it to YouTube.
          </p>
          <a
            href={toAbsoluteUrl(result.preview_url) || result.url}
            target="_blank"
            rel="noopener noreferrer"
            className="source-url"
          >
            Open rendered video preview
          </a>

          <label className="field approval-row">
            <input
              type="checkbox"
              checked={isApprovedForYouTube}
              onChange={(e) => setIsApprovedForYouTube(e.target.checked)}
            />
            <span>I reviewed this video and approve uploading it to YouTube.</span>
          </label>

          <label className="field">
            <span className="field-label">YouTube Title</span>
            <input
              type="text"
              className="field-input"
              value={youtubeTitle}
              onChange={(e) => setYoutubeTitle(e.target.value)}
              maxLength={100}
            />
          </label>

          <label className="field">
            <span className="field-label">YouTube Description</span>
            <textarea
              className="field-input field-textarea"
              value={youtubeDescription}
              onChange={(e) => setYoutubeDescription(e.target.value)}
              rows={3}
            />
          </label>

          <label className="field">
            <span className="field-label">Privacy</span>
            <select
              className="field-input"
              value={youtubePrivacy}
              onChange={(e) => setYoutubePrivacy(e.target.value as "private" | "public" | "unlisted")}
            >
              <option value="private">Private</option>
              <option value="unlisted">Unlisted</option>
              <option value="public">Public</option>
            </select>
          </label>

          <button
            type="button"
            className="button button-primary"
            disabled={isUploadingYouTube || !isApprovedForYouTube}
            onClick={handleUploadToYouTube}
          >
            {isUploadingYouTube ? "Uploading to YouTube..." : "Upload to YouTube"}
          </button>

          {youtubeUploadResult?.success && youtubeUploadResult.youtube_url && (
            <div className="alert alert-success">
              <strong>Uploaded:</strong>{" "}
              <a href={youtubeUploadResult.youtube_url} target="_blank" rel="noopener noreferrer">
                {youtubeUploadResult.youtube_url}
              </a>
            </div>
          )}
        </div>
      )}
    </section>
  );
};


