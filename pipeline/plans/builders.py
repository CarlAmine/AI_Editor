import json
import os
import re
from typing import Any, Dict, List, Optional

MIN_SEG_DUR = 0.7


def _normalize_detected_text(value: Any) -> str:
    if value is None:
        return ""
    txt = " ".join(str(value).split()).strip()
    txt = txt.strip("\"' ")
    txt = re.sub(r"\s*;\s*", " | ", txt)
    return txt


def _compatible_text(a: str, b: str) -> bool:
    if not a or not b:
        return False
    al = a.lower()
    bl = b.lower()
    return al == bl or al in bl or bl in al


def _split_segment_by_scenes(segment: Dict[str, Any], scenes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    start = float(segment.get("start", 0.0))
    end = float(segment.get("end", 0.0))
    text = str(segment.get("text", "")).strip()
    if not text or end <= start:
        return []
    if not scenes:
        return [{"start": start, "end": end, "text": text}]

    out: List[Dict[str, Any]] = []
    cursor = start
    for s in scenes:
        s_start = float(s.get("start_time", 0.0))
        s_end = float(s.get("end_time", 0.0))
        if s_end <= cursor:
            continue
        if s_start >= end:
            break
        cut_start = max(cursor, s_start)
        cut_end = min(end, s_end)
        if cut_end > cut_start:
            out.append({"start": cut_start, "end": cut_end, "text": text})
            cursor = cut_end
        if cursor >= end:
            break
    if not out:
        out.append({"start": start, "end": end, "text": text})
    return out


def build_text_segments(
    analysis: Dict[str, Any],
    video_end: Optional[float] = None,
) -> Dict[str, Any]:
    warnings: List[Dict[str, Any]] = []
    keyframes = analysis.get("keyframes") or []
    scenes = analysis.get("scenes") or []

    if video_end is None:
        scene_end = max((float(s.get("end_time", 0.0)) for s in scenes), default=0.0)
        kf_end = max((float(k.get("timestamp", 0.0)) for k in keyframes), default=0.0)
        video_end = max(scene_end, kf_end)

    points = []
    for k in keyframes:
        try:
            ts = float(k.get("timestamp", 0.0))
        except (TypeError, ValueError):
            continue
        if ts < 0:
            continue
        if video_end is not None and ts > float(video_end) + 1e-6:
            continue
        txt = _normalize_detected_text(k.get("detected_text"))
        points.append({"timestamp": ts, "text": txt})
    points.sort(key=lambda x: x["timestamp"])

    if not points:
        warnings.append(
            {
                "code": "NO_KEYFRAME_TEXT",
                "message": "No keyframe timestamps available to derive text segments.",
                "detail": None,
            }
        )
        return {"segments": [], "warnings": warnings}

    segments: List[Dict[str, Any]] = []
    dropped_empty = 0
    i = 0
    while i < len(points):
        start = points[i]["timestamp"]
        text = points[i]["text"]
        j = i + 1
        while j < len(points) and points[j]["text"] == text:
            j += 1
        end = points[j]["timestamp"] if j < len(points) else float(video_end or start)
        if video_end is not None:
            end = min(end, float(video_end))
        if end > start and text:
            segments.append({"start": start, "end": end, "text": text})
        else:
            dropped_empty += 1
        i = j

    if dropped_empty > 0:
        warnings.append(
            {
                "code": "TEXT_SEGMENTS_DROPPED",
                "message": f"Dropped {dropped_empty} empty/invalid text segments.",
                "detail": {"dropped": dropped_empty},
            }
        )

    # Split across scene boundaries.
    split_segments: List[Dict[str, Any]] = []
    for seg in segments:
        split_segments.extend(_split_segment_by_scenes(seg, scenes))
    segments = split_segments

    # Merge/extend very short segments.
    merged_count = 0
    extended_count = 0
    i = 0
    fixed: List[Dict[str, Any]] = []
    while i < len(segments):
        cur = dict(segments[i])
        dur = float(cur["end"]) - float(cur["start"])
        if dur >= MIN_SEG_DUR:
            fixed.append(cur)
            i += 1
            continue

        nxt = segments[i + 1] if i + 1 < len(segments) else None
        if nxt and _compatible_text(cur["text"], nxt["text"]) and float(nxt["start"]) - float(cur["end"]) < 0.05:
            merged = {
                "start": float(cur["start"]),
                "end": float(nxt["end"]),
                "text": str(nxt["text"]).strip(),
            }
            fixed.append(merged)
            merged_count += 1
            i += 2
            continue

        target_end = float(cur["start"]) + MIN_SEG_DUR
        if nxt:
            target_end = min(target_end, float(nxt["start"]))
        if target_end > float(cur["end"]):
            cur["end"] = target_end
            extended_count += 1
        if float(cur["end"]) > float(cur["start"]):
            fixed.append(cur)
        i += 1

    # Merge adjacent same-text segments with tiny gaps.
    collapsed: List[Dict[str, Any]] = []
    for seg in fixed:
        if not collapsed:
            collapsed.append(seg)
            continue
        prev = collapsed[-1]
        if (
            str(prev.get("text", "")).strip().lower() == str(seg.get("text", "")).strip().lower()
            and float(seg["start"]) - float(prev["end"]) <= 0.1
        ):
            prev["end"] = max(float(prev["end"]), float(seg["end"]))
            merged_count += 1
        else:
            collapsed.append(seg)
    fixed = collapsed

    if merged_count > 0 or extended_count > 0:
        warnings.append(
            {
                "code": "TEXT_SEGMENTS_MERGED",
                "message": "Adjusted short text segments for readability.",
                "detail": {"merged": merged_count, "extended": extended_count, "min_duration": MIN_SEG_DUR},
            }
        )

    return {"segments": fixed, "warnings": warnings}


def _extract_explicit_overlay_texts(requirements: Dict[str, Any]) -> List[str]:
    """
    Parse explicit user overlay instructions from chat state.
    Supported examples:
    - "First overlay text should be Top10 Nature sites"
    - "Second overlay text is Japan"
    - "third overlay text is Italy"
    """
    candidates: List[str] = []
    for key in ("user_requests", "edit_requests"):
        vals = requirements.get(key) or []
        if isinstance(vals, list):
            candidates.extend([str(v) for v in vals if v])

    rank_map = {
        "first": 1,
        "1st": 1,
        "one": 1,
        "second": 2,
        "2nd": 2,
        "two": 2,
        "third": 3,
        "3rd": 3,
        "three": 3,
        "fourth": 4,
        "4th": 4,
        "fifth": 5,
        "5th": 5,
    }
    ranked: Dict[int, str] = {}

    pattern = re.compile(
        r"\b(first|1st|one|second|2nd|two|third|3rd|three|fourth|4th|fifth|5th)\b"
        r".{0,40}?\boverlay\b.{0,20}?\btext\b.{0,20}?\b(?:should be|is|=|:)?\s*(.+)$",
        flags=re.IGNORECASE,
    )
    generic_pattern = re.compile(
        r"\boverlay\b.{0,20}?\btext\b.{0,20}?\b(?:should be|is|=|:)\s*(.+)$",
        flags=re.IGNORECASE,
    )

    for line in candidates:
        m = pattern.search(line.strip())
        if m:
            rank = rank_map.get(m.group(1).lower())
            text = m.group(2).strip().strip("\"' ")
            if rank and text:
                ranked[rank] = text
            continue
        gm = generic_pattern.search(line.strip())
        if gm:
            text = gm.group(1).strip().strip("\"' ")
            if text:
                ranked.setdefault(len(ranked) + 1, text)

    return [ranked[k] for k in sorted(ranked.keys())]


def _collect_request_text(requirements: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ("edit_requests", "user_requests"):
        vals = requirements.get(key) or []
        if isinstance(vals, list):
            parts.extend([str(v) for v in vals if v])
    return "\n".join(parts).strip()


def _wants_ocr_text(requirements: Dict[str, Any]) -> bool:
    blob = _collect_request_text(requirements).lower()
    if not blob:
        return False
    keywords = [
        "use the existing on-screen text",
        "use existing captions",
        "extract from the video",
        "from ocr",
        "existing on-screen text",
    ]
    return any(k in blob for k in keywords)


def _parse_overlay_script(requirements: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    blob = _collect_request_text(requirements)
    if not blob:
        return None
    # Prefer the longest request line; users usually paste the full script there.
    candidate = max([line.strip() for line in blob.splitlines() if line.strip()], key=len, default="")
    if not candidate:
        return None
    # Normalize separators.
    normalized = candidate.replace("\n", " ").replace(";", ",")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    # Try to extract ranked list items like "10. Japan, 9. Korea ... 1. Indonesia".
    item_matches = list(re.finditer(r"(?<!\d)(10|[1-9])\s*[\.\):-]?\s*([^,]+)", normalized))
    if len(item_matches) < 3:
        return None
    items: Dict[int, str] = {}
    for match in item_matches:
        rank = int(match.group(1))
        value = re.sub(r"\s+", " ", match.group(2)).strip(" .,-")
        if value:
            items[rank] = value
    ordered_ranks = sorted(items.keys(), reverse=True)
    ordered_items = [f"{rank}. {items[rank]}" for rank in ordered_ranks]
    if not ordered_items:
        return None
    first_rank_match = re.search(r"(?<!\d)(10|[1-9])\s*[\.\):-]?", normalized)
    title = normalized[: first_rank_match.start()].strip(" .,:-") if first_rank_match else ""
    if not title:
        title = "Top 10"
    return {
        "title": title,
        "items": ordered_items,
        "source": candidate,
    }


def _apply_overlay_text_overrides(
    overlays: List[Dict[str, Any]],
    overrides: List[str],
) -> List[Dict[str, Any]]:
    if not overrides:
        return overlays
    if not overlays:
        # If planner returns nothing, create simple timed placeholders.
        return [
            {"timestamp": float(i * 2), "text": txt, "position": "bottom"}
            for i, txt in enumerate(overrides)
        ]
    updated = list(overlays)
    for i, txt in enumerate(overrides):
        if i >= len(updated):
            break
        item = dict(updated[i])
        item["text"] = txt
        updated[i] = item
    return updated


def write_plan(job_dir: str, filename: str, payload: Dict[str, Any]) -> str:
    plans_dir = os.path.join(job_dir, "plans")
    os.makedirs(plans_dir, exist_ok=True)
    path = os.path.join(plans_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def build_overlay_plan(
    analysis: Dict[str, Any],
    requirements: Dict[str, Any],
    summary: str,
    render_duration: Optional[float] = None,
    analysis_duration: Optional[float] = None,
    montage_mode: bool = False,
) -> Dict[str, Any]:
    warnings: List[Dict[str, Any]] = []
    script = _parse_overlay_script(requirements)
    use_ocr = _wants_ocr_text(requirements) or not script
    overlays: List[Dict[str, Any]] = []
    segments: List[Dict[str, Any]] = []

    if (
        render_duration is not None
        and analysis_duration is not None
        and abs(float(render_duration) - float(analysis_duration)) > 0.25
    ):
        warnings.append(
            {
                "code": "ANALYSIS_RENDER_DURATION_MISMATCH",
                "message": "Analysis and render durations differ; overlays were clipped to rendered timeline.",
                "detail": {
                    "analysis_duration": float(analysis_duration),
                    "render_duration": float(render_duration),
                    "chosen_strategy": "filter_to_render_duration",
                },
            }
        )

    if script and not use_ocr:
        script_lines = [script["title"]] + script["items"]
        overlays = [{"text": line, "position": "top"} for line in script_lines if line]
        warnings.append(
            {
                "code": "OVERLAY_SCRIPT_USED",
                "message": "Using explicit user overlay script instead of OCR text.",
                "detail": {"title": script["title"], "items": len(script["items"])},
            }
        )
    else:
        seg_data = build_text_segments(analysis, video_end=render_duration)
        segments = seg_data.get("segments", [])
        warnings.extend(seg_data.get("warnings", []))
    if segments:
        overlays = [
            {
                "timestamp": float(s["start"]),
                "duration": max(0.0, float(s["end"]) - float(s["start"])),
                "text": s["text"],
                "position": "top",
            }
            for s in segments
        ]
    if not overlays:
        try:
            from ai_editor.overlay_planner import generate_overlay_plan as _generate_overlay_plan

            overlays = _generate_overlay_plan(
                analysis_results=analysis,
                user_prompt=requirements.get("prompt", ""),
                analysis_summary=summary,
                tone=requirements.get("tone"),
                pacing=requirements.get("pacing"),
            )
        except Exception:
            overlays = []
    explicit_texts = _extract_explicit_overlay_texts(requirements)
    if not script:
        overlays = _apply_overlay_text_overrides(overlays or [], explicit_texts)
    overlays = sorted(overlays or [], key=lambda x: float(x.get("timestamp", 0.0)))
    return {
        "overlays": overlays or [],
        "text_segments": segments,
        "warnings": warnings,
        "analysis_duration": analysis_duration,
        "render_duration": render_duration,
        "overlay_script": script,
        "timing_mode": "clip_anchored" if montage_mode else ("ocr_keyframe" if use_ocr else "clip_anchored"),
        "montage_mode": montage_mode,
    }


def build_timeline_plan(
    analysis_scenes: List[Dict[str, Any]],
    source_durations: List[float],
    requirements: Dict[str, Any],
) -> Dict[str, Any]:
    scene_durations = [float(s.get("duration", 0.0)) for s in analysis_scenes if float(s.get("duration", 0.0)) > 0]
    return {
        "scene_durations": scene_durations,
        "source_durations": source_durations,
        "intent_mode": requirements.get("intent_mode", "video"),
    }


def build_audio_plan(inputs: Dict[str, Any], requirements: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "music_mode": requirements.get("music_mode", "original"),
        "custom_music_url": requirements.get("custom_music_url"),
        "soundtrack_url": inputs.get("soundtrack_url"),
        "use_reference_audio_bed": bool(inputs.get("use_reference_audio_bed", False)),
        "mute_source_audio": bool(inputs.get("mute_source_audio", False)),
    }


def build_render_spec(
    timeline_plan: Dict[str, Any],
    overlay_plan: Dict[str, Any],
    audio_plan: Dict[str, Any],
    requirements: Dict[str, Any],
) -> Dict[str, Any]:
    intent = requirements.get("intent_mode", "video")
    output_mode = str(requirements.get("output_mode", "")).lower().strip()
    if not output_mode:
        refit_mode = str(requirements.get("refit_mode", "crop_center")).lower()
        if refit_mode == "native_9x16":
            output_mode = "native_9x16"
        else:
            output_mode = "crop_to_9x16"
    if output_mode not in {"native_9x16", "crop_to_9x16"}:
        output_mode = "crop_to_9x16"

    if intent == "shorts" and output_mode == "crop_to_9x16":
        resolution = "1920x1080"
    else:
        ar = requirements.get("aspect_ratio", "9:16")
        if ar == "16:9":
            resolution = "1920x1080"
        elif ar == "1:1":
            resolution = "1080x1080"
        else:
            resolution = "1080x1920"

    overlay_full_clip = bool(requirements.get("overlay_full_clip", False))
    generation_mode = str(requirements.get("generation_mode", "free_generation_mode")).lower()
    if generation_mode not in {"free_generation_mode", "reference_mimic_mode"}:
        generation_mode = "free_generation_mode"
    return {
        "resolution": resolution,
        "intent_mode": intent,
        "overlay_plan": overlay_plan.get("overlays", []),
        "overlay_script": overlay_plan.get("overlay_script"),
        "timing_mode": overlay_plan.get("timing_mode", "ocr_keyframe"),
        "montage_mode": bool(overlay_plan.get("montage_mode", False)),
        "music_mode": audio_plan.get("music_mode", "original"),
        "soundtrack_url": audio_plan.get("soundtrack_url"),
        "use_reference_audio_bed": bool(audio_plan.get("use_reference_audio_bed", False)),
        "mute_source_audio": bool(audio_plan.get("mute_source_audio", False)),
        "force_mobile_safe_text": intent == "shorts",
        "mobile_safe_text_mode": bool(requirements.get("mobile_safe_text_mode", intent == "shorts")),
        "output_mode": output_mode,
        "refit_mode": "native_9x16" if output_mode == "native_9x16" else "crop_center",
        "overlay_full_clip": overlay_full_clip,
        "generation_mode": generation_mode,
        "disable_auto_transitions": generation_mode == "reference_mimic_mode",
    }


def build_postprocess_plan(requirements: Dict[str, Any]) -> Dict[str, Any]:
    output_mode = str(requirements.get("output_mode", "")).lower().strip()
    if output_mode not in {"native_9x16", "crop_to_9x16"}:
        refit_mode = str(requirements.get("refit_mode", "crop_center")).lower()
        output_mode = "native_9x16" if refit_mode == "native_9x16" else "crop_to_9x16"
    refit_mode = "native_9x16" if output_mode == "native_9x16" else "crop_center"
    return {
        "intent_mode": requirements.get("intent_mode", "video"),
        "refit_mode": refit_mode,
        "output_mode": output_mode,
        "create_shorts": requirements.get("intent_mode", "video") == "shorts" and output_mode == "crop_to_9x16",
        "target_short_resolution": "1080x1920",
        "target_master_name": "master_16x9.mp4",
        "target_short_name": "short_9x16.mp4",
    }
