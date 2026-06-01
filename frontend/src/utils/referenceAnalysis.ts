import type {
  ReferenceAnalysisSummary,
  ReplacementSlot,
  TextMoment,
  TextReplacementEntry,
  TextReplacementAction,
} from "../types/pipeline";

type AnalysisLike = Record<string, unknown>;

function readNumber(value: unknown, fallback = 0): number {
  const parsed = typeof value === "string" ? Number(value) : value;
  return typeof parsed === "number" && Number.isFinite(parsed) ? parsed : fallback;
}

function readString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value.trim() : fallback;
}

function normalizeAspectRatio(value: unknown): string {
  const aspectRatio = readString(value);
  return aspectRatio || "16:9";
}

export function normalizeReferenceSummary(value: unknown): ReferenceAnalysisSummary {
  const summary = (value && typeof value === "object" ? (value as AnalysisLike) : {}) as AnalysisLike;
  const durationSeconds = readNumber(summary.duration_seconds ?? summary.durationSeconds);
  const fps = readNumber(summary.fps, 30);
  const width = Math.max(1, Math.round(readNumber(summary.width, 1920)));
  const height = Math.max(1, Math.round(readNumber(summary.height, 1080)));
  const sceneCount = Math.max(0, Math.round(readNumber(summary.scene_count ?? summary.sceneCount)));
  const styleSummary =
    readString(summary.style_summary ?? summary.styleSummary) ||
    "Reference analysis complete. Review the cards below to continue.";

  return {
    durationSeconds,
    fps,
    width,
    height,
    aspectRatio: normalizeAspectRatio(summary.aspect_ratio ?? summary.aspectRatio),
    sceneCount,
    styleSummary,
  };
}

export function normalizeReplacementSlots(value: unknown): ReplacementSlot[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item, index) => {
      if (!item || typeof item !== "object") return null;
      const slot = item as AnalysisLike;
      const slotId = Math.round(readNumber(slot.slot_id ?? slot.slotId, index + 1));
      const start = readNumber(slot.start_time ?? slot.startTime ?? slot.start);
      const end = readNumber(slot.end_time ?? slot.endTime ?? slot.end);
      const duration = readNumber(slot.duration, Math.max(0, end - start));
      return {
        slotId,
        role: readString(slot.role, "b-roll"),
        start,
        end,
        duration,
        description: readString(slot.description),
      } as ReplacementSlot;
    })
    .filter((item): item is ReplacementSlot => Boolean(item));
}

export function normalizeTextMoments(value: unknown): TextMoment[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item, index) => {
      if (!item || typeof item !== "object") return null;
      const moment = item as AnalysisLike;
      const id = readString(moment.overlay_id ?? moment.id, `text_${index + 1}`);
      return {
        id,
        start: readNumber(moment.start),
        end: readNumber(moment.end),
        detectedText: readString(moment.detected_text ?? moment.detectedText),
        slotId:
          moment.slot_id != null || moment.slotId != null
            ? Math.round(readNumber(moment.slot_id ?? moment.slotId))
            : null,
        approximateTiming: Boolean(moment.approximate_timing ?? moment.approximateTiming),
      } as TextMoment;
    })
    .filter((item): item is TextMoment => Boolean(item && item.detectedText));
}

export function buildDefaultTextReplacements(textMoments: TextMoment[]): TextReplacementEntry[] {
  return textMoments.map((moment) => ({
    id: moment.id,
    start: moment.start,
    end: moment.end,
    detectedText: moment.detectedText,
    action: "keep" satisfies TextReplacementAction,
    text: moment.detectedText,
    slotId: moment.slotId ?? null,
  }));
}

export function normalizeReferenceAnalysis(response: unknown): {
  summary: ReferenceAnalysisSummary;
  slots: ReplacementSlot[];
  textMoments: TextMoment[];
} {
  const payload = (response && typeof response === "object" ? (response as AnalysisLike) : {}) as AnalysisLike;
  const nested = (payload.analysis && typeof payload.analysis === "object"
    ? (payload.analysis as AnalysisLike)
    : {}) as AnalysisLike;

  const summary = normalizeReferenceSummary(
    nested.summary ?? payload.summary ?? payload.reference_summary ?? payload.referenceAnalysis
  );

  const slots = normalizeReplacementSlots(nested.slots ?? payload.slots ?? payload.reference_slots);
  const textMoments = normalizeTextMoments(
    nested.text_moments ?? payload.text_moments ?? payload.text_overlays
  );

  return { summary, slots, textMoments };
}
