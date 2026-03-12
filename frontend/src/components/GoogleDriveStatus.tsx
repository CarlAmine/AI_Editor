/* ============================================================
   GoogleDriveStatus — Show Google Drive OAuth connection status
   ============================================================ */

import { CheckCircle, Circle } from "lucide-react";

interface GoogleDriveStatusProps {
  connected: boolean;
  email: string | null;
  onConnect: () => void;
}

export default function GoogleDriveStatus({ connected, email, onConnect }: GoogleDriveStatusProps) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-6 shadow-sm">
      <h3 className="text-lg font-semibold text-slate-900 mb-4">Google Drive</h3>

      <div className="flex items-start gap-3 mb-4">
        {connected ? (
          <CheckCircle size={20} className="text-green-600 flex-shrink-0 mt-0.5" />
        ) : (
          <Circle size={20} className="text-slate-400 flex-shrink-0 mt-0.5" />
        )}
        <div className="flex-1">
          <p className="text-sm font-medium text-slate-900">
            {connected ? "Connected" : "Not Connected"}
          </p>
          {email && <p className="text-xs text-slate-600 mt-1">{email}</p>}
          {!connected && (
            <p className="text-xs text-slate-600 mt-1">
              Connect to save outputs to Google Drive
            </p>
          )}
        </div>
      </div>

      {!connected && (
        <button
          onClick={onConnect}
          className="w-full px-4 py-2 bg-slate-100 text-slate-900 rounded-md font-medium hover:bg-slate-200 transition"
        >
          Connect Google Drive
        </button>
      )}
    </div>
  );
}
