import React, { useState, FormEvent, ChangeEvent } from "react";

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
  status?: string;
  error?: string;
  render_id?: string;
};

export const VideoPipelinePanel: React.FC<Props> = ({
  apiBase,
  onAnalyzerSummary,
  currentState = {},
}) => {
  const [primaryUrl, setPrimaryUrl] = useState("");
  const [sources, setSources] = useState<VideoSource[]>([]);
  const [newSourceUrl, setNewSourceUrl] = useState("");
  const [newSourceSegments, setNewSourceSegments] = useState<string>("");
  const [prompt, setPrompt] = useState("");
  const [musicMode, setMusicMode] = useState<"original" | "custom">("original");
  const [customMusicUrl, setCustomMusicUrl] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [error, setError] = useState<string | null>(null);

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

    if (!primaryUrl.trim()) {
      setError("Please provide the primary video URL for analysis.");
      return;
    }
    if (sources.length === 0) {
      setError("Please add at least one source video.");
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
      sources: sources,
      prompt: prompt.trim(),
      music_mode: musicMode,
      custom_music_url: musicMode === "custom" ? customMusicUrl.trim() : null,
      requirements_state: currentState || {},
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
        // Clear form on success
        setPrimaryUrl("");
        setSources([]);
        setPrompt("");
        setMusicMode("original");
        setCustomMusicUrl("");
      }
    } catch (err: any) {
      setError(err?.message || "Network error while calling /process-video-url.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="panel">
      <header className="panel-header">
        <h2 className="panel-title">1. Auto‑Edit Your Video</h2>
        <p className="panel-caption">
          Provide YouTube/TikTok URLs, curate clips with timestamps, and render
          a polished edit.
        </p>
      </header>

      <form className="panel-form" onSubmit={handleSubmit}>
        {/* Primary URL for analysis */}
        <label className="field">
          <span className="field-label">
            Primary Video URL (for analysis)
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
          <legend className="field-legend">Source Videos</legend>

          {/* Add new source */}
          <div className="field">
            <span className="field-label">Add Source Video</span>
            <div className="field-group">
              <input
                type="text"
                className="field-input"
                placeholder="Video URL"
                value={newSourceUrl}
                onChange={(e) => setNewSourceUrl(e.target.value)}
              />
              <input
                type="text"
                className="field-input"
                placeholder="Segments (e.g. 10-20, 30-45)"
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
              Leave segments empty to use the entire video. Format: start-end in
              seconds (comma-separated).
            </p>
          </div>

          {/* List of sources */}
          {sources.length > 0 && (
            <div className="sources-list">
              <p className="field-label">Ordered Sources (Final Render Order):</p>
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
                      ↑
                    </button>
                    <button
                      type="button"
                      onClick={() => handleMoveSourceDown(idx)}
                      disabled={idx === sources.length - 1}
                      className="button button-mini"
                      title="Move down"
                    >
                      ↓
                    </button>
                    <button
                      type="button"
                      onClick={() => handleRemoveSource(idx)}
                      className="button button-mini button-danger"
                      title="Remove"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </fieldset>

        {/* Editing Description */}
        <label className="field">
          <span className="field-label">Editing Description</span>
          <textarea
            className="field-input field-textarea"
            placeholder="e.g. Create a 30s vertical highlight reel with upbeat pacing and bold captions."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={4}
          />
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
              <strong>✓ Success!</strong> Your video is ready:{" "}
              <a href={result.url} target="_blank" rel="noopener noreferrer">
                {result.url}
              </a>
            </>
          ) : (
            <>
              <strong>✗ Error:</strong> {result.error}
            </>
          )}
        </div>
      )}
    </section>
  );
};

