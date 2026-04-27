import React from "react";
import { motion } from "framer-motion";
import { AlertCircle, CheckCircle2, Link2, Loader } from "lucide-react";

type ProviderStatus = "connected" | "connecting" | "disconnected" | "error";

interface ProviderCardProps {
  provider: "google-drive" | "health";
  status: ProviderStatus;
  email?: string | null;
  message?: string | null;
  onConnect?: () => void;
  onCheckStatus?: () => void;
  isLoading?: boolean;
}

const getStatusIcon = (status: ProviderStatus) => {
  switch (status) {
    case "connected":
      return <CheckCircle2 size={18} className="text-green-400" />;
    case "connecting":
      return <Loader size={18} className="text-blue-400 animate-spin" />;
    case "error":
      return <AlertCircle size={18} className="text-red-400" />;
    default:
      return <AlertCircle size={18} className="text-gray-400" />;
  }
};

const getStatusColor = (status: ProviderStatus): string => {
  switch (status) {
    case "connected":
      return "border-green-500/30 bg-green-500/5";
    case "connecting":
      return "border-blue-500/30 bg-blue-500/5";
    case "error":
      return "border-red-500/30 bg-red-500/5";
    default:
      return "border-slate-600/40 bg-slate-900/30";
  }
};

const getStatusText = (status: ProviderStatus): string => {
  switch (status) {
    case "connected":
      return "Connected";
    case "connecting":
      return "Connecting";
    case "error":
      return "Error";
    default:
      return "Disconnected";
  }
};

export const ProviderCard: React.FC<ProviderCardProps> = ({
  provider,
  status,
  email,
  message,
  onConnect,
  onCheckStatus,
  isLoading = false,
}) => {
  const config = {
    "google-drive": {
      name: "Google Drive",
      icon: "🔗",
      description: "Connect Drive to pull folder-based source footage.",
      connectLabel: "Connect Drive",
    },
    health: {
      name: "Provider Health",
      icon: "⚙️",
      description: "Check model, render, and storage readiness.",
      connectLabel: "Refresh Health",
    },
  }[provider];

  return (
    <motion.div
      className={`panel p-4 ${getStatusColor(status)}`}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-3 flex-1">
          <div className="text-xl">{config.icon}</div>
          <div className="flex-1">
            <p className="text-sm font-semibold text-slate-100">{config.name}</p>
            <p className="text-xs text-slate-500">{config.description}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs font-medium text-slate-300">
          {getStatusIcon(status)}
          <span>{getStatusText(status)}</span>
        </div>
      </div>

      {email && (
        <div className="mb-3 rounded-lg bg-black/20 px-3 py-2 text-xs text-slate-300">
          <span className="text-slate-500">Connected as:</span> {email}
        </div>
      )}

      {message && <p className="mb-3 text-xs text-slate-400">{message}</p>}

      <div className="flex gap-2">
        {onConnect && (
          <motion.button
            type="button"
            onClick={onConnect}
            disabled={isLoading || status === "connecting"}
            className="flex-1 btn btn-secondary text-xs justify-center"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            {isLoading ? (
              <>
                <Loader size={14} className="animate-spin" />
                Connecting...
              </>
            ) : (
              <>
                <Link2 size={14} />
                {config.connectLabel}
              </>
            )}
          </motion.button>
        )}
        {onCheckStatus && (
          <motion.button
            type="button"
            onClick={onCheckStatus}
            disabled={isLoading}
            className="flex-1 btn btn-secondary text-xs justify-center"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            {isLoading ? (
              <>
                <Loader size={14} className="animate-spin" />
                Checking...
              </>
            ) : (
              "Check Status"
            )}
          </motion.button>
        )}
      </div>
    </motion.div>
  );
};
