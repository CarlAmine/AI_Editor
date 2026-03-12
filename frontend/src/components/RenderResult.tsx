/* ============================================================
   RenderResult — Display render job status and video preview
   ============================================================ */

interface RenderJob {
  job_id: string;
  success: boolean;
  error?: string;
  preview_url?: string;
  url?: string;
}

interface RenderResultProps {
  job: RenderJob;
  onUploadClick: () => void;
}

export default function RenderResult({ job, onUploadClick }: RenderResultProps) {
  const videoUrl = job.preview_url || job.url;

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-6 shadow-sm">
      <h3 className="text-lg font-semibold text-slate-900 mb-4">Render Result</h3>

      {job.success ? (
        <div className="space-y-4">
          <div className="p-3 bg-green-50 border border-green-200 rounded-md">
            <p className="text-sm font-medium text-green-900">✓ Render Successful</p>
            <p className="text-xs text-green-700 mt-1">Job ID: {job.job_id}</p>
          </div>

          {videoUrl && (
            <div>
              <p className="text-sm font-medium text-slate-900 mb-2">Preview</p>
              <video
                src={videoUrl}
                controls
                className="w-full rounded-md bg-black"
                style={{ maxHeight: "300px" }}
              />
              <a
                href={videoUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-blue-600 hover:underline mt-2 inline-block"
              >
                Open in new tab →
              </a>
            </div>
          )}

          <button
            onClick={onUploadClick}
            className="w-full px-4 py-2 bg-green-600 text-white rounded-md font-medium hover:bg-green-700 transition"
          >
            Upload to YouTube
          </button>
        </div>
      ) : (
        <div className="p-3 bg-red-50 border border-red-200 rounded-md">
          <p className="text-sm font-medium text-red-900">✗ Render Failed</p>
          {job.error && <p className="text-xs text-red-700 mt-1">{job.error}</p>}
        </div>
      )}
    </div>
  );
}
