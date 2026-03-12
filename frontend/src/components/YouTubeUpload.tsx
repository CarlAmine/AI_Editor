/* ============================================================
   YouTubeUpload — YouTube upload form with approval checkbox
   ============================================================ */

import { useState } from "react";

interface YouTubeUploadProps {
  onSubmit: (data: {
    title: string;
    description: string;
    privacy_status: string;
  }) => void;
  loading: boolean;
  videoUrl?: string;
}

export default function YouTubeUpload({ onSubmit, loading, videoUrl }: YouTubeUploadProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [privacyStatus, setPrivacyStatus] = useState("unlisted");
  const [approved, setApproved] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!title.trim()) {
      alert("Title is required");
      return;
    }

    if (!approved) {
      alert("Please approve the upload");
      return;
    }

    onSubmit({
      title,
      description,
      privacy_status: privacyStatus,
    });
  };

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-6 shadow-sm">
      <h3 className="text-lg font-semibold text-slate-900 mb-4">Upload to YouTube</h3>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Title */}
        <div>
          <label className="block text-sm font-medium text-slate-900 mb-2">
            Video Title *
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g., Amazing Highlight Reel"
            className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={loading}
          />
        </div>

        {/* Description */}
        <div>
          <label className="block text-sm font-medium text-slate-900 mb-2">
            Description
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Video description..."
            rows={3}
            className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={loading}
          />
        </div>

        {/* Privacy Status */}
        <div>
          <label className="block text-sm font-medium text-slate-900 mb-2">
            Privacy Status
          </label>
          <select
            value={privacyStatus}
            onChange={(e) => setPrivacyStatus(e.target.value)}
            className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={loading}
          >
            <option value="private">Private</option>
            <option value="unlisted">Unlisted</option>
            <option value="public">Public</option>
          </select>
        </div>

        {/* Approval Checkbox */}
        <div className="flex items-start gap-3 p-3 bg-yellow-50 border border-yellow-200 rounded-md">
          <input
            type="checkbox"
            id="approve"
            checked={approved}
            onChange={(e) => setApproved(e.target.checked)}
            className="mt-1 w-4 h-4 accent-yellow-600"
            disabled={loading}
          />
          <label htmlFor="approve" className="text-sm text-slate-900">
            I approve uploading this video to YouTube with the above settings
          </label>
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={loading || !approved}
          className="w-full px-4 py-2 bg-red-600 text-white rounded-md font-medium hover:bg-red-700 disabled:bg-slate-400 disabled:cursor-not-allowed transition"
        >
          {loading ? "Uploading..." : "Upload to YouTube"}
        </button>
      </form>
    </div>
  );
}
