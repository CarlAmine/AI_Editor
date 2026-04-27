import React from "react";
import { motion } from "framer-motion";
import { AlertCircle, CheckCircle2, Clock, Loader, Zap } from "lucide-react";

import { getControllerStatusLabel, type PipelineResult } from "./VideoPipelinePanel";

interface StatusRailProps {
  result: PipelineResult | null;
  isPolling: boolean;
}

type StageState = "pending" | "active" | "complete" | "failed";

const getStatusIcon = (category?: string) => {
  switch (category) {
    case "complete":
      return <CheckCircle2 size={20} className="text-green-400" />;
    case "failed":
      return <AlertCircle size={20} className="text-red-400" />;
    case "blocked":
    case "waiting_for_user_input":
      return <Clock size={20} className="text-amber-400" />;
    case "working":
      return <Zap size={20} className="text-blue-400" />;
    default:
      return <Loader size={20} className="text-slate-400 animate-spin" />;
  }
};

const getStatusShell = (category?: string): string => {
  switch (category) {
    case "complete":
      return "border-green-500/30 bg-green-500/5";
    case "failed":
      return "border-red-500/30 bg-red-500/5";
    case "blocked":
    case "waiting_for_user_input":
      return "border-amber-500/30 bg-amber-500/5";
    case "working":
      return "border-blue-500/30 bg-blue-500/5";
    default:
      return "border-slate-700/40 bg-slate-900/25";
  }
};

const getStageState = (
  stage: "analyze" | "plan" | "render" | "complete",
  result: PipelineResult
): StageState => {
  const status = result.controller_status;
  const category = result.controller_status_category;

  if (category === "failed") {
    if (stage === "complete") return "failed";
    if (stage === "render" && status === "rendering") return "failed";
    if (
      stage === "plan" &&
      [
        "planning",
        "revising",
        "validating",
        "awaiting_user_input",
        "blocked_by_unapplied_edits",
        "revision_limit_exhausted",
      ].includes(status || "")
    ) {
      return "failed";
    }
  }

  if (category === "blocked" || category === "waiting_for_user_input") {
    if (stage === "plan") return "active";
  }

  if (category === "complete") {
    return "complete";
  }

  switch (stage) {
    case "analyze":
      if (status === "analyzing") return "active";
      if (status) return "complete";
      return "pending";
    case "plan":
      if (
        [
          "planning",
          "revising",
          "validating",
          "awaiting_user_input",
          "blocked_by_unapplied_edits",
          "revision_limit_exhausted",
        ].includes(status || "")
      ) {
        return "active";
      }
      if (status === "rendering" || category === "complete") return "complete";
      return "pending";
    case "render":
      if (status === "rendering") return "active";
      if (category === "complete") return "complete";
      return "pending";
    case "complete":
      return category === "complete" ? "complete" : "pending";
  }
};

const StageDot: React.FC<{
  label: string;
  state: StageState;
}> = ({ label, state }) => {
  const shell =
    state === "complete"
      ? "border-green-500 bg-green-500/10"
      : state === "failed"
        ? "border-red-500 bg-red-500/10"
        : state === "active"
          ? "border-blue-500 bg-blue-500/10"
          : "border-slate-600 bg-slate-900/20";

  return (
    <motion.div
      className="flex flex-col items-center gap-2 min-w-[56px]"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <motion.div
        className={`w-10 h-10 rounded-full flex items-center justify-center border-2 ${shell}`}
        animate={state === "active" ? { scale: [1, 1.08, 1] } : {}}
        transition={state === "active" ? { duration: 1.4, repeat: Infinity } : {}}
      >
        {state === "complete" ? (
          <CheckCircle2 size={18} className="text-green-400" />
        ) : state === "failed" ? (
          <AlertCircle size={18} className="text-red-400" />
        ) : state === "active" ? (
          <Loader size={18} className="text-blue-400 animate-spin" />
        ) : (
          <div className="w-2 h-2 rounded-full bg-slate-600" />
        )}
      </motion.div>
      <span className="text-[11px] font-medium text-slate-400 text-center">{label}</span>
    </motion.div>
  );
};

export const StatusRail: React.FC<StatusRailProps> = ({ result, isPolling }) => {
  if (!result) {
    return (
      <motion.div
        className="panel p-6 text-center"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45 }}
      >
        <p className="text-slate-400 text-sm">
          Submit your pipeline configuration to begin tracking controller progress.
        </p>
      </motion.div>
    );
  }

  const category = result.controller_status_category;
  const stages = [
    { key: "analyze" as const, label: "Analyze" },
    { key: "plan" as const, label: "Plan" },
    { key: "render" as const, label: "Render" },
    { key: "complete" as const, label: "Done" },
  ];

  return (
    <motion.div
      className={`panel p-6 space-y-6 ${getStatusShell(category)}`}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay: 0.1 }}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          {getStatusIcon(category)}
          <div>
            <p className="text-sm font-semibold text-slate-100">
              {getControllerStatusLabel(result)}
            </p>
            {result.controller_status && (
              <p className="text-xs text-slate-400 mt-1">{result.controller_status}</p>
            )}
            {result.controller_status_detail && (
              <p className="text-xs text-slate-500 mt-1">
                {result.controller_status_detail}
              </p>
            )}
          </div>
        </div>

        {isPolling && (
          <motion.div
            className="text-xs px-2 py-1 rounded-full bg-blue-500/20 text-blue-300 flex items-center gap-1"
            animate={{ opacity: [0.5, 1, 0.5] }}
            transition={{ duration: 1.8, repeat: Infinity }}
          >
            <Loader size={12} className="animate-spin" />
            Polling
          </motion.div>
        )}
      </div>

      <div className="flex items-start justify-between gap-2">
        {stages.map((stage, idx) => (
          <div key={stage.key} className="flex items-start flex-1 gap-2">
            <StageDot label={stage.label} state={getStageState(stage.key, result)} />
            {idx < stages.length - 1 && (
              <div className="flex-1 h-0.5 mt-5 bg-slate-700/80 rounded-full" />
            )}
          </div>
        ))}
      </div>

      {result.user_notice && (
        <div className="rounded-lg bg-amber-500/10 border border-amber-500/30 p-3 text-xs text-amber-200">
          {result.user_notice}
        </div>
      )}

      {result.error && (
        <div className="rounded-lg bg-red-500/10 border border-red-500/30 p-3 text-xs text-red-200">
          <p className="font-semibold mb-1">Error</p>
          <p>{result.error}</p>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 pt-4 border-t border-slate-700/50">
        <div>
          <p className="text-xs text-slate-500">Decisions</p>
          <p className="text-sm font-semibold text-slate-200">
            {result.decision_trace_count ?? 0}
          </p>
        </div>
        {result.project_id && (
          <div>
            <p className="text-xs text-slate-500">Project ID</p>
            <p className="text-xs font-mono text-slate-300 truncate">{result.project_id}</p>
          </div>
        )}
      </div>
    </motion.div>
  );
};
