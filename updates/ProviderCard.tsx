import React from "react";
import { motion } from "framer-motion";
import { CheckCircle2, AlertCircle, Loader, Link2 } from "lucide-react";

interface ProviderCardProps {
  provider: "google-drive" | "health";
  status: "connected" | "connecting" | "disconnected" | "error";
  email?: string | null;
  message?: string | null;
  onConnect?: () => void;
  onCheckStatus?: () => void;
  isLoading?: boolean;
}

const getStatusIcon = (status: string) => {
  switch (status) {
    case "connected":
      return <CheckCircle2 size={20} className="text-green-400" />;
    case "connecting":
      return <Loader size={20} className="text-blue-400 animate-spin" />;
    case "error":
      return <AlertCircle size={20} className="text-red-400" />;
    default:
      return <AlertCircle size={20} className="text-gray-400" />;
  }
};

const getStatusColor = (status: string): string => {
  switch (status) {
    case "connected":
      return "border-green-500/30 bg-green-500/5";
    case "connecting":
      return "border-blue-500/30 bg-blue-500/5";
    case "error":
      return "border-red-500/30 bg-red-500/5";
    default:
      return "border-gray-500/30 bg-gray-500/5";
  }
};

const getStatusText = (status: string): string => {
  switch (status) {
    case "connected":
      return "Connected";
    case "connecting":
      return "Connecting...";
    case "error":
      return "Connection Error";
    default:
      return "Disconnected";
  }
};

const getStatusTextColor = (status: string): string => {
  switch (status) {
    case "connected":
      return "text-green-300";
    case "connecting":
      return "text-blue-300";
    case "error":
      return "text-red-300";
    default:
      return "text-gray-300";
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
  const providerConfig = {
    "google-drive": {
      name: "Google Drive",
      icon: "🔗",
      description: "Connect to load source files from your Drive",
      connectLabel: "Connect Google Drive",
    },
    health: {
      name: "Provider Health",
      icon: "⚙️",
      description: "Check the status of external providers",
      connectLabel: "Check Status",
    },
  };

  const config = providerConfig[provider];

  return (
    <motion.div
      className={`panel p-4 ${getStatusColor(status)}`}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-3 flex-1">
          <div className="text-xl">{config.icon}</div>
          <div className="flex-1">
            <p className="text-sm font-semibold text-gray-100">{config.name}</p>
            <p className="text-xs text-gray-500">{config.description}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {getStatusIcon(status)}
          <span className={`text-xs font-medium ${getStatusTextColor(status)}`}>
            {getStatusText(status)}
          </span>
        </div>
      </div>

      {/* Email Display */}
      {email && (
        <motion.div
          className="mb-3 p-2 rounded-lg bg-black/20 text-xs text-gray-300"
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          exit={{ opacity: 0, height: 0 }}
        >
          <span className="text-gray-500">Connected as:</span> {email}
        </motion.div>
      )}

      {/* Message Display */}
      {message && (
        <motion.p
          className="text-xs text-gray-400 mb-3 italic"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3 }}
        >
          {message}
        </motion.p>
      )}

      {/* Actions */}
      <div className="flex gap-2">
        {onConnect && (
          <motion.button
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
