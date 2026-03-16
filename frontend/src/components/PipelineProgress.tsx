import React, { useEffect, useRef, useState } from "react";
import { Check, X } from "lucide-react";

export type PipelineStage = "analyzing" | "editing" | "rendering" | "done";
export type StageStatus = "pending" | "active" | "complete" | "failed";

export interface StageState {
  stage: PipelineStage;
  status: StageStatus;
}

interface Props {
  currentStage: PipelineStage | null;
  failed?: boolean;
}

const STAGES: { id: PipelineStage; label: string }[] = [
  { id: "analyzing", label: "Analyzing" },
  { id: "editing", label: "Editing" },
  { id: "rendering", label: "Rendering" },
  { id: "done", label: "Done" },
];

const STAGE_ORDER: PipelineStage[] = ["analyzing", "editing", "rendering", "done"];

function getStageStatus(
  stageId: PipelineStage,
  currentStage: PipelineStage | null,
  failed: boolean
): StageStatus {
  if (!currentStage) return "pending";
  const currentIdx = STAGE_ORDER.indexOf(currentStage);
  const stageIdx = STAGE_ORDER.indexOf(stageId);
  if (stageIdx < currentIdx) return "complete";
  if (stageIdx === currentIdx) return failed ? "failed" : "active";
  return "pending";
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0");
  const s = (seconds % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

export const PipelineProgress: React.FC<Props> = ({
  currentStage,
  failed = false,
}) => {
  const [elapsed, setElapsed] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (currentStage && currentStage !== "done" && !failed) {
      intervalRef.current = setInterval(() => {
        setElapsed((prev) => prev + 1);
      }, 1000);
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [currentStage, failed]);

  // Reset elapsed when pipeline starts fresh
  useEffect(() => {
    if (currentStage === "analyzing") {
      setElapsed(0);
    }
  }, [currentStage]);

  if (!currentStage) return null;

  return (
    <div className="pipeline-progress">
      <div className="pipeline-progress-steps">
        {STAGES.map((stage, idx) => {
          const status = getStageStatus(stage.id, currentStage, failed);
          return (
            <React.Fragment key={stage.id}>
              <div className={`progress-step progress-step--${status}`}>
                <div className="progress-node">
                  {status === "complete" ? (
                    <Check size={14} strokeWidth={2.5} />
                  ) : status === "failed" ? (
                    <X size={14} strokeWidth={2.5} />
                  ) : (
                    <span className="progress-node-dot" />
                  )}
                </div>
                <span className="progress-step-label">{stage.label}</span>
              </div>
              {idx < STAGES.length - 1 && (
                <div
                  className={`progress-connector ${
                    getStageStatus(STAGES[idx + 1].id, currentStage, failed) !== "pending" ||
                    status === "complete"
                      ? "progress-connector--filled"
                      : ""
                  }`}
                />
              )}
            </React.Fragment>
          );
        })}
      </div>
      <div className="pipeline-progress-timer">
        <span className="progress-timer-label">Elapsed</span>
        <span className="progress-timer-value">{formatTime(elapsed)}</span>
      </div>
    </div>
  );
};
