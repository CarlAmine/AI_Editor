/* ============================================================
   Pipeline Page — Functional video rendering interface
   Connects to FastAPI backend for end-to-end video editing
   ============================================================ */

import { useState, useEffect } from "react";
import RenderForm from "../components/RenderForm";
import RenderResult from "../components/RenderResult";
import YouTubeUpload from "../components/YouTubeUpload";
import ErrorBanner from "../components/ErrorBanner";
import GoogleDriveStatus from "../components/GoogleDriveStatus";
import { motion } from "framer-motion";

interface RenderJob {
  job_id: string;
  success: boolean;
  error?: string;
  preview_url?: string;
  url?: string;
}

export default function Pipeline() {
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
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.4 }}
      className="min-h-screen pt-20"
    >
      {/* Header */}
      <div className="bg-gradient-to-b from-slate-900 to-slate-800 text-white py-12 border-b border-slate-700">
        <div className="container mx-auto px-6 max-w-7xl">
          <div className="section-number mb-3">FUNCTIONAL INTERFACE</div>
          <h1
            className="text-5xl md:text-6xl font-bold mb-3"
            style={{
              fontFamily: "'Bebas Neue', sans-serif",
              letterSpacing: "0.02em",
            }}
          >
            RENDER PIPELINE
          </h1>
          <p className="text-slate-300 text-lg max-w-2xl">
            End-to-end video editing with AI analysis, cloud rendering, and YouTube publishing.
          </p>
        </div>
      </div>

      {/* Main Content */}
      <main className="container mx-auto px-6 py-12 max-w-7xl">
        {error && <ErrorBanner message={error} onClose={() => setError(null)} />}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left: Form */}
          <motion.div
            className="lg:col-span-2"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
          >
            <div
              className="rounded-lg p-8 border"
              style={{
                background: "oklch(0.13 0.015 265)",
                borderColor: "oklch(1 0 0 / 8%)",
              }}
            >
              <h2
                className="text-2xl font-bold mb-6"
                style={{
                  fontFamily: "'Bebas Neue', sans-serif",
                  color: "oklch(0.93 0.01 80)",
                }}
              >
                RENDER CONFIGURATION
              </h2>
              <RenderForm
                onSubmit={handleRenderSubmit}
                loading={loading}
                apiBaseUrl={apiBaseUrl}
                googleDriveConnected={googleDriveConnected}
                onGoogleDriveConnect={handleGoogleDriveConnect}
              />
            </div>
          </motion.div>

          {/* Right: Status & Results */}
          <motion.div
            className="space-y-6"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
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
          </motion.div>
        </div>
      </main>
    </motion.div>
  );
}
