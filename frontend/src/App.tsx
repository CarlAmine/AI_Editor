/* ============================================================
   AI EDITOR FUNCTIONAL FRONTEND
   Connects to FastAPI backend for video rendering & YouTube upload
   ============================================================ */

import { useState, useEffect } from "react";
import RenderForm from "./components/RenderForm";
import RenderResult from "./components/RenderResult";
import YouTubeUpload from "./components/YouTubeUpload";
import ErrorBanner from "./components/ErrorBanner";
import GoogleDriveStatus from "./components/GoogleDriveStatus";

interface RenderJob {
  job_id: string;
  success: boolean;
  error?: string;
  preview_url?: string;
  url?: string;
}

export default function App() {
  const [apiBaseUrl] = useState(
    import.meta.env.VITE_API_BASE_URL || "http://localhost:10000"
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [renderJob, setRenderJob] = useState<RenderJob | null>(null);
  const [googleDriveConnected, setGoogleDriveConnected] = useState(false);
  const [googleDriveEmail, setGoogleDriveEmail] = useState<string | null>(null);

  // Check Google Drive OAuth status on mount
  useEffect(() => {
    checkGoogleDriveStatus();
  }, []);

  const checkGoogleDriveStatus = async () => {
    try {
      const response = await fetch(`${apiBaseUrl}/google-drive/oauth/status`);
      if (response.ok) {
        const data = await response.json();
        if (data.connected) {
          setGoogleDriveConnected(true);
          setGoogleDriveEmail(data.email || null);
        }
      }
    } catch (err) {
      console.log("Google Drive not connected");
    }
  };

  const handleRenderSubmit = async (formData: {
    primary_url: string;
    sources: Array<{ url: string; segments?: Array<{ start: string; end: string }> }>;
    prompt: string;
    intent_mode: string;
    music_mode: string;
    custom_music_url?: string;
    custom_music_segment?: string;
    google_drive_link?: string;
  }) => {
    setLoading(true);
    setError(null);
    setRenderJob(null);

    try {
      const payload = {
        primary_url: formData.primary_url,
        sources: formData.sources,
        prompt: formData.prompt,
        music_mode: formData.music_mode,
        custom_music_url: formData.custom_music_url || null,
        custom_music_segment: formData.custom_music_segment || null,
        google_drive_link: formData.google_drive_link || null,
        requirements_state: {
          intent_mode: formData.intent_mode,
        },
      };

      const response = await fetch(`${apiBaseUrl}/process-video-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (!response.ok) {
        setError(data.error || "Failed to start render job");
        return;
      }

      setRenderJob(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error occurred");
    } finally {
      setLoading(false);
    }
  };

  const handleYouTubeUpload = async (uploadData: {
    title: string;
    description: string;
    privacy_status: string;
  }) => {
    if (!renderJob) return;

    setLoading(true);
    setError(null);

    try {
      const payload = {
        render_url: renderJob.preview_url || renderJob.url,
        title: uploadData.title,
        description: uploadData.description,
        privacy_status: uploadData.privacy_status,
        project_id: renderJob.job_id,
      };

      const response = await fetch(`${apiBaseUrl}/upload-approved-video-youtube`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (!response.ok) {
        setError(data.error || "Failed to upload to YouTube");
        return;
      }

      setError(null);
      alert(`Video uploaded successfully! Video ID: ${data.video_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error occurred");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleDriveConnect = async () => {
    try {
      const response = await fetch(`${apiBaseUrl}/google-drive/oauth/start`);
      const data = await response.json();
      if (data.auth_url) {
        window.open(data.auth_url, "_blank");
        // Poll for status after a delay
        setTimeout(checkGoogleDriveStatus, 2000);
      }
    } catch (err) {
      setError("Failed to initiate Google Drive connection");
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <h1 className="text-2xl font-bold text-slate-900">AI Editor Pipeline</h1>
          <p className="text-sm text-slate-600 mt-1">
            Render videos end-to-end with AI-powered editing
          </p>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {error && <ErrorBanner message={error} onClose={() => setError(null)} />}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left: Form */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-lg border border-slate-200 p-6 shadow-sm">
              <h2 className="text-xl font-semibold text-slate-900 mb-6">Render Configuration</h2>
              <RenderForm
                onSubmit={handleRenderSubmit}
                loading={loading}
                apiBaseUrl={apiBaseUrl}
                googleDriveConnected={googleDriveConnected}
                onGoogleDriveConnect={handleGoogleDriveConnect}
              />
            </div>
          </div>

          {/* Right: Status & Results */}
          <div className="space-y-6">
            {/* Google Drive Status */}
            <GoogleDriveStatus
              connected={googleDriveConnected}
              email={googleDriveEmail}
              onConnect={handleGoogleDriveConnect}
            />

            {/* Render Result */}
            {renderJob && (
              <RenderResult
                job={renderJob}
                onUploadClick={() => {
                  // Scroll to YouTube upload section
                  const uploadSection = document.getElementById("youtube-upload");
                  uploadSection?.scrollIntoView({ behavior: "smooth" });
                }}
              />
            )}

            {/* YouTube Upload */}
            {renderJob && renderJob.success && (
              <div id="youtube-upload">
                <YouTubeUpload
                  onSubmit={handleYouTubeUpload}
                  loading={loading}
                  videoUrl={renderJob.preview_url || renderJob.url}
                />
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
