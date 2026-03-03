import React, { useState, FormEvent, ChangeEvent } from "react";

type Props = {
  apiBase: string;
  onAnalyzerSummary?: (summary: string) => void;
};

type PipelineResult = {
  success?: boolean;
  url?: string;
  status?: string;
  error?: string;
  dashboard_url?: string;
};

export const VideoPipelinePanel: React.FC<Props> = ({
  apiBase,
  onAnalyzerSummary,
}) => {
  const [prompt, setPrompt] = useState("");
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [folderId, setFolderId] = useState("");
  const [musicUrl, setMusicUrl] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    setResult(null);
    setError(null);
    const file = e.target.files?.[0];
    if (file) {
      setVideoFile(file);
    } else {
      setVideoFile(null);
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setResult(null);

    if (!videoFile) {
      setError("Please select a video file to upload.");
      return;
    }
    if (!prompt.trim()) {
      setError("Please provide a short description of the edit you want.");
      return;
    }

    const formData = new FormData();
    formData.append("prompt", prompt);
    formData.append("video", videoFile);
    if (folderId.trim()) {
      formData.append("folder_id", folderId.trim());
    }
    if (musicUrl.trim()) {
      formData.append("music_url", musicUrl.trim());
    }

    setIsSubmitting(true);

    try {
      const response = await fetch(`${apiBase}/process-video`, {
        method: "POST",
        body: formData,
      });

      const data: PipelineResult = await response.json();
      setResult(data);

      // If the backend prints/returns an analysis summary later, you can
      // pipe it back into the chat via onAnalyzerSummary. For now we
      // simply send the prompt as context.
      if (onAnalyzerSummary) {
        onAnalyzerSummary(`User edit brief: ${prompt}`);
      }

      if (!response.ok || data.success === false) {
        setError(
          data.error ||
            "The pipeline reported a failure. Please check server logs for details."
        );
      }
    } catch (err: any) {
      setError(err?.message || "Network error while calling /process-video.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="panel">
      <header className="panel-header">
        <h2 className="panel-title">1. Auto‑Edit Your Video</h2>
        <p className="panel-caption">
          Upload a clip, describe the edit you want, and let the pipeline
          analyze, assemble and render.
        </p>
      </header>

      <form className="panel-form" onSubmit={handleSubmit}>
        <label className="field">
          <span className="field-label">Video file</span>
          <input
            type="file"
            accept="video/*"
            onChange={handleFileChange}
            className="field-input"
          />
        </label>

        <label className="field">
          <span className="field-label">Edit description</span>
          <textarea
            className="field-input field-textarea"
            placeholder="e.g. Create a 30s vertical highlight reel with upbeat pacing and bold captions."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={4}
          />
        </label>

        <div className="field-grid">
          <label className="field">
            <span className="field-label optional">
              Google Drive Folder ID <span>(optional)</span>
            </span>
            <input
              className="field-input"
              placeholder="Override VIDEO_FOLDER from .env"
              value={folderId}
              onChange={(e) => setFolderId(e.target.value)}
            />
          </label>

          <label className="field">
            <span className="field-label optional">
              Music URL <span>(optional)</span>
            </span>
            <input
              className="field-input"
              placeholder="Override MUSIC_URL from .env"
              value={musicUrl}
              onChange={(e) => setMusicUrl(e.target.value)}
            />
          </label>
        </div>

        {error && <div className="alert alert-error">{error}</div>}

        <button
          type="submit"
          className="btn btn-primary"
          disabled={isSubmitting}
        >
          {isSubmitting ? "Processing…" : "Run pipeline"}
        </button>
      </form>

      <div className="panel-result">
        {isSubmitting && (
          <p className="status-text">Submitting render job and polling status…</p>
        )}
        {result && (
          <div className="result-card">
            <p className="status-line">
              <span className="status-label">Status:</span>{" "}
              <span className="status-value">{result.status || "unknown"}</span>
            </p>
            {result.url && (
              <p className="status-line">
                <span className="status-label">Rendered URL:</span>{" "}
                <a
                  href={result.url}
                  target="_blank"
                  rel="noreferrer"
                  className="link"
                >
                  Open video
                </a>
              </p>
            )}
            {result.dashboard_url && (
              <p className="status-line">
                <span className="status-label">Shotstack dashboard:</span>{" "}
                <a
                  href={result.dashboard_url}
                  target="_blank"
                  rel="noreferrer"
                  className="link"
                >
                  View job
                </a>
              </p>
            )}
          </div>
        )}
      </div>
    </section>
  );
};

