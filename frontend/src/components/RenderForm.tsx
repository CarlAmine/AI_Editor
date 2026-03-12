/* ============================================================
   RenderForm — Video rendering configuration form
   ============================================================ */

import { useState } from "react";

interface Source {
  url: string;
  segments?: Array<{ start: string; end: string }>;
}

interface RenderFormProps {
  onSubmit: (data: {
    primary_url: string;
    sources: Source[];
    prompt: string;
    intent_mode: string;
    music_mode: string;
    custom_music_url?: string;
    custom_music_segment?: string;
    google_drive_link?: string;
  }) => void;
  loading: boolean;
  apiBaseUrl: string;
  googleDriveConnected: boolean;
  onGoogleDriveConnect: () => void;
}

export default function RenderForm({
  onSubmit,
  loading,
  googleDriveConnected,
  onGoogleDriveConnect,
}: RenderFormProps) {
  const [primaryUrl, setPrimaryUrl] = useState("");
  const [sources, setSources] = useState<Source[]>([]);
  const [bulkImport, setBulkImport] = useState("");
  const [prompt, setPrompt] = useState("");
  const [intentMode, setIntentMode] = useState("video");
  const [musicMode, setMusicMode] = useState("original");
  const [customMusicUrl, setCustomMusicUrl] = useState("");
  const [customMusicSegment, setCustomMusicSegment] = useState("0:00-0:13");
  const [googleDriveLink, setGoogleDriveLink] = useState("");

  const parseTimeToSeconds = (time: string): number => {
    const parts = time.split(":").map(Number);
    if (parts.length === 3) {
      return parts[0] * 3600 + parts[1] * 60 + parts[2];
    } else if (parts.length === 2) {
      return parts[0] * 60 + parts[1];
    }
    return parseInt(time) || 0;
  };

  const parseSegment = (segmentStr: string): { start: string; end: string } | null => {
    const match = segmentStr.match(/(\d+:?\d*:?\d*)-(\d+:?\d*:?\d*)/);
    if (!match) return null;
    return { start: match[1], end: match[2] };
  };

  const handleBulkImport = () => {
    const lines = bulkImport.trim().split("\n");
    const newSources: Source[] = [];

    lines.forEach((line) => {
      line = line.trim();
      if (!line) return;

      // Format: URL - segment1, segment2, ...
      const parts = line.split(" - ");
      const url = parts[0].trim();
      const segments: Array<{ start: string; end: string }> = [];

      if (parts[1]) {
        const segmentParts = parts[1].split(",");
        segmentParts.forEach((seg) => {
          const parsed = parseSegment(seg.trim());
          if (parsed) segments.push(parsed);
        });
      }

      newSources.push({ url, ...(segments.length > 0 && { segments }) });
    });

    setSources(newSources);
    setBulkImport("");
  };

  const addSource = () => {
    setSources([...sources, { url: "" }]);
  };

  const updateSource = (index: number, field: string, value: any) => {
    const newSources = [...sources];
    if (field === "url") {
      newSources[index].url = value;
    } else if (field === "segments") {
      newSources[index].segments = value;
    }
    setSources(newSources);
  };

  const removeSource = (index: number) => {
    setSources(sources.filter((_, i) => i !== index));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!primaryUrl.trim()) {
      alert("Primary URL is required");
      return;
    }

    if (sources.length === 0) {
      alert("At least one source is required");
      return;
    }

    if (!prompt.trim()) {
      alert("Prompt/brief is required");
      return;
    }

    const payload = {
      primary_url: primaryUrl,
      sources,
      prompt,
      intent_mode: intentMode,
      music_mode: musicMode,
      custom_music_url: musicMode === "custom" ? customMusicUrl : undefined,
      custom_music_segment: musicMode === "custom" ? customMusicSegment : undefined,
      google_drive_link: googleDriveLink || undefined,
    };

    onSubmit(payload);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Primary URL */}
      <div>
        <label className="block text-sm font-medium text-slate-900 mb-2">
          Primary Reference Video URL *
        </label>
        <input
          type="url"
          value={primaryUrl}
          onChange={(e) => setPrimaryUrl(e.target.value)}
          placeholder="https://youtube.com/watch?v=..."
          className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          disabled={loading}
        />
      </div>

      {/* Sources */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <label className="block text-sm font-medium text-slate-900">
            Video Sources *
          </label>
          <button
            type="button"
            onClick={addSource}
            className="text-xs px-3 py-1 bg-blue-50 text-blue-700 rounded hover:bg-blue-100 disabled:opacity-50"
            disabled={loading}
          >
            + Add Source
          </button>
        </div>

        {sources.length === 0 && (
          <p className="text-xs text-slate-500 mb-3">No sources added. Use bulk import or add manually.</p>
        )}

        {sources.map((source, idx) => (
          <div key={idx} className="mb-4 p-3 bg-slate-50 rounded-md border border-slate-200">
            <div className="flex gap-2 mb-2">
              <input
                type="url"
                value={source.url}
                onChange={(e) => updateSource(idx, "url", e.target.value)}
                placeholder="https://youtube.com/watch?v=..."
                className="flex-1 px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={loading}
              />
              <button
                type="button"
                onClick={() => removeSource(idx)}
                className="px-3 py-2 bg-red-50 text-red-700 text-sm rounded hover:bg-red-100 disabled:opacity-50"
                disabled={loading}
              >
                Remove
              </button>
            </div>
            <p className="text-xs text-slate-600">Optional: Add segments in format "0:10-0:25, 1:00-1:15"</p>
          </div>
        ))}

        {/* Bulk Import */}
        <div className="mt-4 p-3 bg-slate-50 rounded-md border border-slate-200">
          <label className="block text-xs font-medium text-slate-900 mb-2">
            Bulk Import (one per line)
          </label>
          <textarea
            value={bulkImport}
            onChange={(e) => setBulkImport(e.target.value)}
            placeholder="https://youtube.com/watch?v=... - 0:10-0:25, 1:00-1:15&#10;https://youtube.com/watch?v=..."
            rows={3}
            className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
            disabled={loading}
          />
          <button
            type="button"
            onClick={handleBulkImport}
            className="mt-2 text-xs px-3 py-1 bg-slate-200 text-slate-700 rounded hover:bg-slate-300 disabled:opacity-50"
            disabled={loading || !bulkImport.trim()}
          >
            Import
          </button>
        </div>
      </div>

      {/* Prompt */}
      <div>
        <label className="block text-sm font-medium text-slate-900 mb-2">
          Prompt / Brief *
        </label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="e.g., Create a 60-second highlight reel with upbeat music and text overlays"
          rows={4}
          className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          disabled={loading}
        />
      </div>

      {/* Intent Mode */}
      <div>
        <label className="block text-sm font-medium text-slate-900 mb-2">
          Intent Mode
        </label>
        <select
          value={intentMode}
          onChange={(e) => setIntentMode(e.target.value)}
          className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          disabled={loading}
        >
          <option value="video">Video (16:9)</option>
          <option value="shorts">Shorts (9:16)</option>
        </select>
      </div>

      {/* Music Mode */}
      <div>
        <label className="block text-sm font-medium text-slate-900 mb-2">
          Music Mode
        </label>
        <select
          value={musicMode}
          onChange={(e) => setMusicMode(e.target.value)}
          className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          disabled={loading}
        >
          <option value="original">Original (from source)</option>
          <option value="custom">Custom Music</option>
        </select>
      </div>

      {/* Custom Music */}
      {musicMode === "custom" && (
        <div className="space-y-3 p-3 bg-blue-50 rounded-md border border-blue-200">
          <div>
            <label className="block text-sm font-medium text-slate-900 mb-2">
              Custom Music URL
            </label>
            <input
              type="url"
              value={customMusicUrl}
              onChange={(e) => setCustomMusicUrl(e.target.value)}
              placeholder="https://..."
              className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={loading}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-900 mb-2">
              Music Segment (HH:MM:SS or MM:SS)
            </label>
            <input
              type="text"
              value={customMusicSegment}
              onChange={(e) => setCustomMusicSegment(e.target.value)}
              placeholder="0:00-0:13"
              className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
              disabled={loading}
            />
          </div>
        </div>
      )}

      {/* Google Drive */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="block text-sm font-medium text-slate-900">
            Google Drive
          </label>
          <button
            type="button"
            onClick={onGoogleDriveConnect}
            className={`text-xs px-3 py-1 rounded ${
              googleDriveConnected
                ? "bg-green-50 text-green-700"
                : "bg-slate-200 text-slate-700 hover:bg-slate-300"
            }`}
            disabled={loading}
          >
            {googleDriveConnected ? "✓ Connected" : "Connect"}
          </button>
        </div>
        <input
          type="url"
          value={googleDriveLink}
          onChange={(e) => setGoogleDriveLink(e.target.value)}
          placeholder="https://drive.google.com/drive/folders/..."
          className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          disabled={loading}
        />
        <p className="text-xs text-slate-600 mt-1">Optional: Folder to save outputs</p>
      </div>

      {/* Submit */}
      <button
        type="submit"
        disabled={loading}
        className="w-full px-4 py-2 bg-blue-600 text-white rounded-md font-medium hover:bg-blue-700 disabled:bg-slate-400 disabled:cursor-not-allowed transition"
      >
        {loading ? "Processing..." : "Start Render"}
      </button>
    </form>
  );
}
