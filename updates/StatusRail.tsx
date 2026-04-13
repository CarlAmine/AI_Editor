import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle2, AlertCircle, Clock, Zap, Loader } from "lucide-react";
import { PipelineResult, getControllerStatusLabel } from "./VideoPipelinePanel";

interface StatusRailProps {
  result: PipelineResult | null;
  isPolling: boolean;
  apiBase: string;
}

const getStatusIcon = (status: string | undefined, category: string | undefined) => {
  if (category === "complete") {
    return <CheckCircle2 size={20} className="text-green-400" />;
  }
  if (category === "failed") {
    return <AlertCircle size={20} className="text-red-400" />;
  }
  if (category === "blocked" || category === "waiting_for_user_input") {
    return <Clock size={20} className="text-yellow-400" />;
  }
  if (category === "working") {
    return <Zap size={20} className="text-blue-400" />;
  }
  return <Loader size={20} className="text-gray-400 animate-spin" />;
};

const getStatusColor = (category: string | undefined): string => {
  switch (category) {
    case "complete":
      return "border-green-500/30 bg-green-500/5";
    case "failed":
      return "border-red-500/30 bg-red-500/5";
    case "blocked":
    case "waiting_for_user_input":
      return "border-yellow-500/30 bg-yellow-500/5";
    case "working":
      return "border-blue-500/30 bg-blue-500/5";
    default:
      return "border-gray-500/30 bg-gray-500/5";
  }
};

const getStatusTextColor = (category: string | undefined): string => {
  switch (category) {
    case "complete":
      return "text-green-300";
    case "failed":
      return "text-red-300";
    case "blocked":
    case "waiting_for_user_input":
      return "text-yellow-300";
    case "working":
      return "text-blue-300";
    default:
      return "text-gray-300";
  }
};

const ProgressStage: React.FC<{
  stage: string;
  label: string;
  isActive: boolean;
  isComplete: boolean;
  isFailed: boolean;
}> = ({ stage, label, isActive, isComplete, isFailed }) => {
  return (
    <motion.div
      className="flex flex-col items-center gap-2"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      <motion.div
        className={`w-10 h-10 rounded-full flex items-center justify-center border-2 transition-all ${
          isComplete
            ? "border-green-500 bg-green-500/10"
            : isFailed
              ? "border-red-500 bg-red-500/10"
              : isActive
                ? "border-blue-500 bg-blue-500/10"
                : "border-gray-600 bg-gray-900/20"
        }`}
        animate={isActive ? { scale: [1, 1.1, 1] } : {}}
        transition={isActive ? { duration: 1.5, repeat: Infinity } : {}}
      >
        {isComplete ? (
          <CheckCircle2 size={18} className="text-green-400" />
        ) : isFailed ? (
          <AlertCircle size={18} className="text-red-400" />
        ) : isActive ? (
          <Loader size={18} className="text-blue-400 animate-spin" />
        ) : (
          <div className="w-2 h-2 rounded-full bg-gray-600" />
        )}
      </motion.div>
      <span className="text-xs font-medium text-gray-400">{label}</span>
    </motion.div>
  );
};

export const StatusRail: React.FC<StatusRailProps> = ({ result, isPolling, apiBase }) => {
  if (!result) {
    return (
      <motion.div
        className="panel p-6 text-center"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <p className="text-gray-400 text-sm">
          Submit your pipeline configuration to begin tracking progress.
        </p>
      </motion.div>
    );
  }

  const category = result.controller_status_category;
  const status = result.controller_status;
  const statusLabel = getStatusLabel(result);

  // Determine which stages are complete/active/failed
  const stages = [
    {
      id: "setup",
      label: "Setup",
      isActive: category === "working" && status !== "rendering",
      isComplete: ["editing", "rendering", "done"].some((s) => status?.includes(s)),
      isFailed: category === "failed" || category === "blocked",
    },
    {
      id: "editing",
      label: "Editing",
      isActive: status === "editing" || status?.includes("editing"),
      isComplete: ["rendering", "done"].some((s) => status?.includes(s)),
      isFailed: category === "failed",
    },
    {
      id: "rendering",
      label: "Rendering",
      isActive: status === "rendering",
      isComplete: category === "complete",
      isFailed: category === "failed",
    },
    {
      id: "done",
      label: "Complete",
      isActive: false,
      isComplete: category === "complete",
      isFailed: category === "failed",
    },
  ];

  return (
    <motion.div
      className={`panel p-6 space-y-6 ${getStatusColor(category)}`}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.1 }}
    >
      {/* Status Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          {getStatusIcon(status, category)}
          <div>
            <p className={`text-sm font-semibold ${getStatusTextColor(category)}`}>
              {statusLabel}
            </p>
            {result.controller_status_detail && (
              <p className="text-xs text-gray-400 mt-1">{result.controller_status_detail}</p>
            )}
          </div>
        </div>
        {isPolling && (
          <motion.div
            className="text-xs px-2 py-1 rounded-full bg-blue-500/20 text-blue-300 flex items-center gap-1"
            animate={{ opacity: [0.5, 1, 0.5] }}
            transition={{ duration: 2, repeat: Infinity }}
          >
            <Loader size={12} className="animate-spin" />
            Polling
          </motion.div>
        )}
      </div>

      {/* Progress Stages */}
      <div className="flex justify-between items-start">
        {stages.map((stage, idx) => (
          <React.Fragment key={stage.id}>
            <ProgressStage
              stage={stage.id}
              label={stage.label}
              isActive={!!stage.isActive}
              isComplete={stage.isComplete}
              isFailed={stage.isFailed}
            />
            {idx < stages.length - 1 && (
              <motion.div
                className={`flex-1 h-0.5 mx-2 mt-5 ${
                  stage.isComplete ? "bg-green-500" : "bg-gray-700"
                }`}
                initial={{ scaleX: 0 }}
                animate={{ scaleX: 1 }}
                transition={{ duration: 0.6, delay: idx * 0.1 }}
              />
            )}
          </React.Fragment>
        ))}
      </div>

      {/* Status Details */}
      <AnimatePresence>
        {result.user_notice && (
          <motion.div
            className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/30 text-xs text-yellow-300"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
          >
            {result.user_notice}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Additional Metrics */}
      {result.decision_trace_count !== undefined && (
        <div className="grid grid-cols-2 gap-3 pt-4 border-t border-gray-700/50">
          <div>
            <p className="text-xs text-gray-500">Decisions</p>
            <p className="text-sm font-semibold text-gray-300">{result.decision_trace_count}</p>
          </div>
          {result.project_id && (
            <div>
              <p className="text-xs text-gray-500">Project ID</p>
              <p className="text-xs font-mono text-gray-400 truncate">{result.project_id}</p>
            </div>
          )}
        </div>
      )}

      {/* Error Display */}
      {result.error && (
        <motion.div
          className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-xs text-red-300"
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          exit={{ opacity: 0, height: 0 }}
        >
          <p className="font-semibold mb-1">Error</p>
          <p>{result.error}</p>
        </motion.div>
      )}
    </motion.div>
  );
};

function getStatusLabel(result: PipelineResult): string {
  const category = result.controller_status_category;
  const status = result.controller_status;

  if (category === "working") {
    if (status === "rendering") return "🎬 Rendering...";
    if (status?.includes("editing")) return "✏️ Editing...";
    return "⚙️ Processing...";
  }

  if (category === "waiting_for_user_input") {
    return "⏸️ Awaiting Input";
  }

  if (category === "blocked") {
    return "🚫 Blocked";
  }

  if (category === "complete") {
    return "✅ Complete";
  }

  if (category === "failed") {
    return "❌ Failed";
  }

  return result.success ? "✅ Complete" : "❌ Failed";
}
