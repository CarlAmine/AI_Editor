import type {
  ProcessVideoURLPayload,
  SlotMappingEntry,
  TextReplacementEntry,
  VideoSource,
} from "../types/pipeline";

function asString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function asNumber(value: unknown, fallback = 0): number {
  const parsed = typeof value === "string" ? Number(value) : value;
  return typeof parsed === "number" && Number.isFinite(parsed) ? parsed : fallback;
}

export function buildPromptFromState(state: Record<string, unknown>): string {
  if (asString(state.prompt)) {
    return asString(state.prompt);
  }

  const lines: string[] = ["Replicate the reference editing style with the provided replacements."];

  if (asString(state.primary_url)) {
    lines.push(`Reference video: ${asString(state.primary_url)}`);
  }

  if (asString(state.reference_style_summary)) {
    lines.push(`Style summary: ${asString(state.reference_style_summary)}`);
  }

  if (asString(state.aspect_ratio)) {
    lines.push(`Output format: ${asString(state.aspect_ratio)}`);
  }

  if (asString(state.refit_mode)) {
    lines.push(`Refit mode: ${asString(state.refit_mode)}`);
  }

  return lines.join("\n");
}

function normalizeSlotMapping(state: Record<string, unknown>): SlotMappingEntry[] {
  const referenceSlots = Array.isArray(state.reference_slots) ? state.reference_slots : [];
  const mapping = Array.isArray(state.slot_mapping) ? state.slot_mapping : [];

  if (mapping.length > 0) {
    return mapping
      .map((item, index) => {
        if (!item || typeof item !== "object") return null;
        const row = item as Record<string, unknown>;
        const slotId = Math.round(asNumber(row.slot_id ?? row.slotId, index + 1));
        const clipUrl = asString(row.clip_url ?? row.clipUrl);
        const clipId = asString(row.clip_id ?? row.clipId) || `slot_${slotId}`;
        return {
          slot_id: slotId,
          clip_id: clipId,
          clip_url: clipUrl,
          source_start: row.source_start != null ? asNumber(row.source_start) : undefined,
          source_end: row.source_end != null ? asNumber(row.source_end) : undefined,
        } as SlotMappingEntry;
      })
      .filter((entry) => Boolean(entry?.clip_url || entry?.clip_id)) as SlotMappingEntry[];
  }

  return referenceSlots.map((slot, index) => {
    const row = slot as Record<string, unknown>;
    const slotId = Math.round(asNumber(row.slot_id ?? row.slotId, index + 1));
    return {
      slot_id: slotId,
      clip_id: `slot_${slotId}`,
      clip_url: "",
      source_start: 0,
      source_end: asNumber(row.duration ?? 0),
    } as SlotMappingEntry;
  });
}

function normalizeTextReplacements(state: Record<string, unknown>): TextReplacementEntry[] {
  const replacements = Array.isArray(state.text_replacements) ? state.text_replacements : [];
  const textMoments = Array.isArray(state.text_moments) ? state.text_moments : [];
  const textOverlays = Array.isArray(state.text_overlays) ? state.text_overlays : [];
  const sourceRows = replacements.length > 0 ? replacements : textMoments.length > 0 ? textMoments : textOverlays;

  return sourceRows
    .map((item, index) => {
      if (!item || typeof item !== "object") return null;
      const row = item as Record<string, unknown>;
      const id = asString(row.id ?? row.overlay_id) || `text_${index + 1}`;
      const detectedText = asString(row.detectedText ?? row.detected_text);
      const action = asString(row.action).toLowerCase();
      const normalizedAction =
        action === "remove" || action === "replace" || action === "keep" ? action : "keep";
      const text =
        normalizedAction === "remove"
          ? ""
          : normalizedAction === "replace"
            ? asString(row.text ?? row.render_text)
            : detectedText;

      return {
        id,
        start: asNumber(row.start),
        end: asNumber(row.end),
        detectedText,
        action: normalizedAction as TextReplacementEntry["action"],
        text,
        slotId:
          row.slotId != null || row.slot_id != null
            ? Math.round(asNumber(row.slotId ?? row.slot_id))
            : null,
      } as TextReplacementEntry;
    })
    .filter((entry) => Boolean(entry?.id)) as TextReplacementEntry[];
}

function buildTextOverlayPayload(replacements: TextReplacementEntry[]) {
  return replacements.map((item) => {
    const action = item.action === "replace" ? "render" : item.action;
    return {
      overlay_id: item.id,
      slot_id: item.slotId ?? null,
      start: item.start,
      end: item.end,
      detected_text: item.detectedText,
      render_text: item.action === "remove" ? "" : item.text,
      action,
      position: "center",
      approximate_timing: false,
    };
  });
}

export function buildPipelinePayloadFromChatState(
  state: Record<string, unknown>
): ProcessVideoURLPayload {
  const primary_url = asString(state.primary_url);
  const referenceSlots = Array.isArray(state.reference_slots) ? state.reference_slots : [];
  const slotMapping = normalizeSlotMapping(state);
  const textReplacements = normalizeTextReplacements(state);
  const textOverlays = buildTextOverlayPayload(textReplacements);

  const filledSlotMapping = slotMapping.map((entry, index) => {
    const referenceSlot = referenceSlots[index] as Record<string, unknown> | undefined;
    const duration = referenceSlot ? asNumber(referenceSlot.duration, 0) : asNumber(entry.source_end, 0);
    const clipUrl = entry.clip_url || asString(state.shared_target_video_url);
    return {
      ...entry,
      clip_url: clipUrl,
      clip_id: entry.clip_id || `slot_${entry.slot_id}`,
      source_start: entry.source_start ?? 0,
      source_end: entry.source_end ?? duration,
    };
  });

  const sources: VideoSource[] = filledSlotMapping.map((entry) => ({
    label: entry.slot_id,
    url: entry.clip_url,
    clip_id: entry.clip_id,
    id: entry.clip_id,
    start: entry.source_start,
    end: entry.source_end,
    segments:
      entry.source_start != null && entry.source_end != null
        ? [{ start: entry.source_start, end: entry.source_end }]
        : undefined,
  }));

  const music_mode = asString(state.music_mode) === "custom" ? "custom" : "original";
  const custom_music_url = music_mode === "custom" ? asString(state.custom_music_url) || null : null;
  const custom_music_segment = music_mode === "custom" ? asString(state.custom_music_segment) || null : null;
  const google_drive_link = asString(state.google_drive_link) || null;
  const aspect_ratio = asString(state.aspect_ratio);
  const intent_mode = asString(state.intent_mode) || (aspect_ratio === "9:16" ? "shorts" : "video");
  const generation_mode = asString(state.generation_mode) || "reference_style_transfer";

  const requirements_state = {
    ...state,
    intent_mode,
    aspect_ratio,
    generation_mode,
    slot_mapping: filledSlotMapping,
    text_replacements: textReplacements,
    text_overlays: textOverlays,
    text_overlays_resolved: textReplacements.length === 0 || textReplacements.every((item) => item.action !== "replace" || item.text.trim().length > 0),
  };

  return {
    primary_url,
    sources,
    prompt: buildPromptFromState(state),
    music_mode,
    custom_music_url,
    custom_music_segment,
    google_drive_link,
    requirements_state,
    slot_mapping: filledSlotMapping,
  };
}
