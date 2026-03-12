/* ============================================================
   ErrorBanner — Display error messages with dismiss button
   ============================================================ */

import { X } from "lucide-react";

interface ErrorBannerProps {
  message: string;
  onClose: () => void;
}

export default function ErrorBanner({ message, onClose }: ErrorBannerProps) {
  return (
    <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
      <div className="flex-1">
        <p className="text-sm font-medium text-red-900">Error</p>
        <p className="text-sm text-red-700 mt-1">{message}</p>
      </div>
      <button
        onClick={onClose}
        className="text-red-600 hover:text-red-700 flex-shrink-0"
        aria-label="Close"
      >
        <X size={18} />
      </button>
    </div>
  );
}
