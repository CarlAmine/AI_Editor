export type VideoSegment = {
  start: number;
  end: number;
};

export type VideoSource = {
  label: number;
  url: string;
  clip_id?: string;
  id?: string;
  start?: number;
  end?: number;
  segments?: VideoSegment[];
};

export type SlotMappingEntry = {
  slot_id: number;
  clip_id: string;
  clip_url: string;
  source_start?: number;
  source_end?: number;
};

export type TextReplacementAction = "keep" | "remove" | "replace";

export type TextExtractedStyle = {
  textColor: string;
  bgColor: string;
  hasBackground: boolean;
  fontSizeEst: number;
  isBold: boolean;
};

export type TextReplacementEntry = {
  id: string;
  start: number;
  end: number;
  detectedText: string;
  action: TextReplacementAction;
  text: string;
  slotId?: number | null;
  /** Normalised 4-point bbox [[x1,y1],[x2,y2],[x3,y3],[x4,y4]] in [0,1] range */
  bbox?: number[][] | null;
  /** Where in the frame the text appeared: "Top" | "Middle" | "Bottom" */
  detectedPosition?: string | null;
  /** Visual style sampled from the source frame */
  extractedStyle?: TextExtractedStyle | null;
};

export type ReplacementSlot = {
  slotId: number;
  role: string;
  start: number;
  end: number;
  duration: number;
  description?: string;
};

export type TextMoment = {
  id: string;
  start: number;
  end: number;
  detectedText: string;
  slotId?: number | null;
  approximateTiming?: boolean;
};

export type ReferenceAnalysisSummary = {
  durationSeconds: number;
  fps: number;
  width: number;
  height: number;
  aspectRatio: string;
  sceneCount: number;
  styleSummary: string;
};

export type ProcessVideoURLPayload = {
  primary_url: string;
  sources: VideoSource[];
  prompt: string;
  music_mode: "original" | "custom";
  custom_music_url: string | null;
  custom_music_segment: string | null;
  google_drive_link: string | null;
  requirements_state: Record<string, unknown>;
  slot_mapping: SlotMappingEntry[];
};

export type IntakePhase =
  | "awaiting_reference"
  | "analyzing_reference"
  | "reference_url_received"
  | "reference_summary_ready"
  | "awaiting_sources"
  | "awaiting_slot_mapping"
  | "awaiting_audio"
  | "awaiting_custom_music"
  | "awaiting_output"
  | "awaiting_final_confirmation"
  | "pipeline_running";

export type ReferenceSlot = {
  slot_id: number;
  start_time: number;
  end_time: number;
  duration: number;
  role: string;
  description: string;
};

export type ReferenceSummary = {
  duration_seconds: number;
  fps: number;
  width: number;
  height: number;
  aspect_ratio: string;
  scene_count: number;
  style_summary: string;
};
