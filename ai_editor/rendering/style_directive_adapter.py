from __future__ import annotations

from typing import Any, Dict, List, Optional


class StyleDirectiveAdapter:
    """Translate deferred editing directives into additive render settings."""

    def adapt(
        self,
        timeline_plan: Dict[str, Any],
        overlay_plan: Dict[str, Any],
        requirements: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        requirements = requirements or {}
        directives = list(timeline_plan.get("edit_directives") or [])
        overlays = [dict(item) for item in (overlay_plan.get("overlays") or [])]
        text_segments = [dict(item) for item in (overlay_plan.get("text_segments") or [])]

        settings: Dict[str, Any] = {
            "caption_density_mode": "normal",
            "caption_style_preset": "default",
            "overlay_density_cap": None,
            "text_placement_policy": "default",
            "text_readability_mode": "balanced",
        }
        applied: List[Dict[str, Any]] = []
        deferred: List[Dict[str, Any]] = []

        for directive in directives:
            operation = str(directive.get("operation", "")).strip().lower()
            if operation == "increase_captions":
                settings["caption_density_mode"] = "dense"
                applied.append(directive)
                continue
            if operation == "decrease_captions":
                settings["caption_density_mode"] = "sparse"
                settings["text_readability_mode"] = "conservative"
                applied.append(directive)
                continue
            if operation == "increase_overlay_density":
                settings["caption_density_mode"] = "dense"
                applied.append(directive)
                continue
            if operation == "decrease_overlay_density":
                settings["caption_density_mode"] = "sparse"
                settings["text_placement_policy"] = "top_safe"
                settings["text_readability_mode"] = "conservative"
                applied.append(directive)
                continue
            if operation == "change_caption_style":
                preset = self._caption_style_preset(str(directive.get("value", "")))
                if preset is not None:
                    settings["caption_style_preset"] = preset
                    applied.append(directive)
                else:
                    deferred.append(directive)
                continue
            if operation == "less_cluttered":
                settings["caption_density_mode"] = "sparse"
                settings["text_placement_policy"] = "top_safe"
                settings["text_readability_mode"] = "conservative"
                applied.append(directive)
                continue
            if operation == "more_cluttered":
                settings["caption_density_mode"] = "dense"
                applied.append(directive)
                continue
            deferred.append(directive)

        adapted_overlays = self._apply_density_policy(
            overlays=overlays,
            text_segments=text_segments,
            density_mode=str(settings["caption_density_mode"]),
        )
        adapted_overlays = self._apply_placement_policy(adapted_overlays, str(settings["text_placement_policy"]))
        settings["overlay_density_cap"] = len(adapted_overlays) if settings["caption_density_mode"] == "sparse" else None

        return {
            "overlay_plan": adapted_overlays,
            "render_settings": settings,
            "applied_directives": applied,
            "deferred_directives": deferred,
        }

    def _apply_density_policy(
        self,
        overlays: List[Dict[str, Any]],
        text_segments: List[Dict[str, Any]],
        density_mode: str,
    ) -> List[Dict[str, Any]]:
        if density_mode == "dense":
            if text_segments and len(text_segments) > len(overlays):
                return [
                    {
                        "timestamp": float(item.get("start", 0.0)),
                        "duration": max(0.7, float(item.get("end", 0.0)) - float(item.get("start", 0.0))),
                        "text": str(item.get("text", "")).strip(),
                        "position": "top",
                    }
                    for item in text_segments
                    if str(item.get("text", "")).strip()
                ]
            return overlays
        if density_mode == "sparse":
            if not overlays:
                return overlays
            filtered = [item for index, item in enumerate(overlays) if index % 2 == 0]
            return filtered or overlays[:1]
        return overlays

    def _apply_placement_policy(self, overlays: List[Dict[str, Any]], placement_policy: str) -> List[Dict[str, Any]]:
        if placement_policy != "top_safe":
            return overlays
        updated: List[Dict[str, Any]] = []
        for item in overlays:
            entry = dict(item)
            entry["position"] = "top"
            updated.append(entry)
        return updated

    def _caption_style_preset(self, value: str) -> str | None:
        normalized = " ".join(str(value or "").strip().lower().split())
        if not normalized:
            return None
        if "bold" in normalized and "minimal" in normalized:
            return "bold_minimal"
        if "minimal" in normalized:
            return "minimal"
        if "compact" in normalized:
            return "compact"
        if "default" in normalized:
            return "default"
        return None
