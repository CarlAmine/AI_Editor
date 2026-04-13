import React, { useState } from "react";
import { Youtube, Upload, ExternalLink } from "lucide-react";

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

interface Props {
  result: PipelineResult;
  apiBase: string;
  onPublished?: (ytResult: YouTubeUploadResult) => void;
}

export const YouTubePublishStep: React.FC<Props> = ({
  result,
  apiBase,
  onPublished,
}) => {
  const toAbsoluteUrl = (value?: string | null): string => {
    if (!value) return "";
    if (value.startsWith("/")) return `${apiBase}${value}`;
    return value;
  };

  const previewUrl = toAbsoluteUrl(result.preview_url) || result.url || "";

  const [isApproved, setIsApproved] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [privacy, setPrivacy] = useState<"private" | "public" | "unlisted">("private");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<YouTubeUploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dismissError, setDismissError] = useState(false);

  const handleUpload = async () => {
    if (!isApproved) {
      setError("Please review and approve the video before uploading.");
      setDismissError(false);
      return;
    }
    if (!title.trim()) {
      setError("Please enter a YouTube title.");
      setDismissError(false);
      return;
    }

    setError(null);
    setDismissError(false);
    setUploadResult(null);
    setIsUploading(true);

    try {
      const uploadSourceUrl = (result.preview_url || result.url || "").startsWith("/")
        ? `${apiBase}${result.preview_url || result.url}`
        : result.preview_url || result.url || "";

      const response = await fetch(`${apiBase}/upload-approved-video-youtube`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          render_url: uploadSourceUrl,
          title: title.trim(),
          description: description.trim(),
          privacy_status: privacy,
          tags: [],
          category_id: "22",
          made_for_kids: false,
          project_id: result.project_id || null,
        }),
      });

      const data: YouTubeUploadResult = await response.json();
      setUploadResult(data);

      if (!response.ok || data.success === false) {
        setError(data.error || "YouTube upload failed.");
      } else if (onPublished) {
        onPublished(data);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Network error during YouTube upload.";
      setError(message);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="yt-publish-card">
      <div className="yt-publish-header">
        <div className="yt-publish-icon">
          <Youtube size={22} />
        </div>
        <div>
          <h3 className="yt-publish-title">Publish to YouTube</h3>
          <p className="yt-publish-subtitle">
            Review your rendered video, then upload it directly to your channel.
          </p>
        </div>
      </div>

      {previewUrl && (
        <div className="yt-video-preview">
          <video
            className="yt-video-player"
            src={previewUrl}
            controls
            preload="metadata"
          />
        </div>
      )}

      {error && !dismissError && (
        <div className="alert alert-error">
          <span>{error}</span>
          <button
            type="button"
            className="alert-dismiss"
            onClick={() => setDismissError(true)}
            aria-label="Dismiss"
          >
            ×
          </button>
        </div>
      )}

      {uploadResult?.success && uploadResult.youtube_url ? (
        <div className="alert alert-success">
          <strong>Uploaded!</strong>{" "}
          <a
            href={uploadResult.youtube_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            View on YouTube <ExternalLink size={12} style={{ display: "inline", verticalAlign: "middle" }} />
          </a>
        </div>
      ) : (
        <>
          <label className="yt-approval-toggle">
            <div
              className={`yt-toggle-track ${isApproved ? "yt-toggle-track--on" : ""}`}
              onClick={() => setIsApproved((v) => !v)}
              role="checkbox"
              aria-checked={isApproved}
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === " " || e.key === "Enter") setIsApproved((v) => !v);
              }}
            >
              <div className="yt-toggle-thumb" />
            </div>
            <span className="yt-approval-label">
              I reviewed this video and approve uploading it to YouTube.
            </span>
          </label>

          <label className="field">
            <span className="field-label field-label--prominent">YouTube Title</span>
            <input
              type="text"
              className="field-input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={100}
              placeholder="Enter a title for your video"
            />
          </label>

          <label className="field">
            <span className="field-label">YouTube Description</span>
            <textarea
              className="field-input field-textarea"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="Optional description..."
            />
          </label>

          <label className="field">
            <span className="field-label">Privacy</span>
            <div className="select-wrapper">
              <select
                className="field-input field-select"
                value={privacy}
                onChange={(e) =>
                  setPrivacy(e.target.value as "private" | "public" | "unlisted")
                }
              >
                <option value="private">Private</option>
                <option value="unlisted">Unlisted</option>
                <option value="public">Public</option>
              </select>
            </div>
          </label>

          <button
            type="button"
            className="btn btn-primary btn-large"
            disabled={isUploading || !isApproved}
            onClick={handleUpload}
          >
            {isUploading ? (
              <>
                <span className="btn-spinner" />
                Uploading...
              </>
            ) : (
              <>
                <Upload size={18} />
                Upload to YouTube
              </>
            )}
          </button>
        </>
      )}
    </div>
  );
};
