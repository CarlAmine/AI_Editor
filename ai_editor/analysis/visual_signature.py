from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence

try:
    import cv2
except Exception:  # pragma: no cover - dependency availability varies by environment
    cv2 = None  # type: ignore

try:
    import numpy as np
except Exception:  # pragma: no cover - dependency availability varies by environment
    np = None  # type: ignore

from .analysis_schema import Segment


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


class VisualSignatureAnalyzer:
    """Builds lightweight visual signatures from sampled frames and annotates segments."""

    def describe_frame(self, frame: Any) -> Dict[str, Any]:
        if cv2 is None or np is None or frame is None:
            return self._empty_signature()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(gray))
        contrast = float(np.std(gray))
        edges = cv2.Canny(gray, 80, 160)
        edge_density = float(np.count_nonzero(edges)) / float(edges.size or 1)

        hist_b = cv2.calcHist([frame], [0], None, [4], [0, 256]).flatten()
        hist_g = cv2.calcHist([frame], [1], None, [4], [0, 256]).flatten()
        hist_r = cv2.calcHist([frame], [2], None, [4], [0, 256]).flatten()
        hist = np.concatenate([hist_b, hist_g, hist_r]).astype("float32")
        hist_sum = float(hist.sum() or 1.0)
        hist = hist / hist_sum

        small = cv2.resize(gray, (8, 8), interpolation=cv2.INTER_AREA)
        mean_val = float(np.mean(small))
        ahash_bits = "".join("1" if float(value) >= mean_val else "0" for value in small.flatten())

        mean_bgr = np.mean(frame.reshape(-1, 3), axis=0)
        dominant_channel = ["blue", "green", "red"][int(np.argmax(mean_bgr))]

        return {
            "brightness": round(brightness, 4),
            "contrast": round(contrast, 4),
            "edge_density": round(edge_density, 6),
            "mean_bgr": [round(float(value), 4) for value in mean_bgr.tolist()],
            "color_histogram": [round(float(value), 6) for value in hist.tolist()],
            "ahash": ahash_bits,
            "dominant_channel": dominant_channel,
        }

    def annotate_segments(self, segments: Sequence[Segment], keyframes: Iterable[Dict[str, Any]]) -> List[Segment]:
        prepared_keyframes = [self._normalize_keyframe(item) for item in keyframes]
        cluster_centers: List[Dict[str, Any]] = []
        previous_signature: Dict[str, Any] | None = None

        for segment in sorted(segments, key=lambda item: float(item.start)):
            matched = self._keyframes_for_segment(segment, prepared_keyframes)
            signature = self._aggregate_signatures(matched)
            novelty = self._novelty(signature, previous_signature)
            cluster_id = self._cluster_for_signature(signature, cluster_centers)

            segment.visual_signature = signature
            segment.novelty_score = round(novelty, 4)
            segment.visual_cluster_id = cluster_id
            segment.metadata["visual_signature_ready"] = bool(signature.get("sample_count"))
            segment.metadata["visual_sample_count"] = int(signature.get("sample_count", 0))
            segment.metadata["visual_cluster_id"] = cluster_id
            previous_signature = signature
        return list(segments)

    def similarity(self, left: Dict[str, Any], right: Dict[str, Any]) -> float:
        left_hist = left.get("color_histogram") or []
        right_hist = right.get("color_histogram") or []
        hist_distance = self._hist_distance(left_hist, right_hist)
        brightness_gap = abs(float(left.get("brightness", 0.0)) - float(right.get("brightness", 0.0))) / 255.0
        contrast_gap = abs(float(left.get("contrast", 0.0)) - float(right.get("contrast", 0.0))) / 128.0
        edge_gap = abs(float(left.get("edge_density", 0.0)) - float(right.get("edge_density", 0.0)))
        hash_gap = self._hash_distance(str(left.get("ahash", "")), str(right.get("ahash", "")))
        distance = (
            0.45 * hist_distance
            + 0.2 * min(brightness_gap, 1.0)
            + 0.15 * min(contrast_gap, 1.0)
            + 0.1 * min(edge_gap * 4.0, 1.0)
            + 0.1 * hash_gap
        )
        return round(_clamp(1.0 - distance), 4)

    def _normalize_keyframe(self, item: Dict[str, Any]) -> Dict[str, Any]:
        output = dict(item)
        signature = output.get("visual_signature")
        if not isinstance(signature, dict):
            signature = {
                "brightness": float(output.get("brightness", 0.0) or 0.0),
                "contrast": float(output.get("contrast", 0.0) or 0.0),
                "edge_density": float(output.get("edge_density", 0.0) or 0.0),
                "mean_bgr": list(output.get("mean_bgr") or [0.0, 0.0, 0.0]),
                "color_histogram": list(output.get("color_histogram") or [0.0] * 12),
                "ahash": str(output.get("ahash", "")),
                "dominant_channel": str(output.get("dominant_channel", "unknown")),
            }
        output["visual_signature"] = signature
        return output

    def _keyframes_for_segment(self, segment: Segment, keyframes: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        start = float(segment.start)
        end = float(segment.end)
        matched = [item for item in keyframes if start <= float(item.get("timestamp", -1.0)) <= end + 1e-6]
        if matched:
            return matched
        midpoint = (start + end) / 2.0
        nearest = min(
            keyframes,
            key=lambda item: abs(float(item.get("timestamp", 0.0)) - midpoint),
            default=None,
        )
        return [nearest] if nearest is not None else []

    def _aggregate_signatures(self, keyframes: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        if not keyframes:
            return self._empty_signature()
        signatures = [item.get("visual_signature") or self._empty_signature() for item in keyframes]
        count = len(signatures)
        mean_bgr = [
            round(sum(float(signature.get("mean_bgr", [0.0, 0.0, 0.0])[idx]) for signature in signatures) / count, 4)
            for idx in range(3)
        ]
        histogram_length = len(signatures[0].get("color_histogram") or [])
        histogram = [
            round(sum(float(signature.get("color_histogram", [0.0] * histogram_length)[idx]) for signature in signatures) / count, 6)
            for idx in range(histogram_length)
        ]
        ahash = max(
            (str(signature.get("ahash", "")) for signature in signatures),
            key=lambda value: value.count("1"),
            default="",
        )
        brightness = sum(float(signature.get("brightness", 0.0)) for signature in signatures) / count
        contrast = sum(float(signature.get("contrast", 0.0)) for signature in signatures) / count
        edge_density = sum(float(signature.get("edge_density", 0.0)) for signature in signatures) / count
        dominant_votes: Dict[str, int] = {}
        for signature in signatures:
            dominant = str(signature.get("dominant_channel", "unknown"))
            dominant_votes[dominant] = dominant_votes.get(dominant, 0) + 1
        dominant_channel = sorted(dominant_votes.items(), key=lambda item: (-item[1], item[0]))[0][0]
        return {
            "sample_count": count,
            "brightness": round(brightness, 4),
            "contrast": round(contrast, 4),
            "edge_density": round(edge_density, 6),
            "mean_bgr": mean_bgr,
            "color_histogram": histogram,
            "ahash": ahash,
            "dominant_channel": dominant_channel,
        }

    def _novelty(self, signature: Dict[str, Any], previous_signature: Dict[str, Any] | None) -> float:
        if previous_signature is None or not previous_signature.get("sample_count"):
            return 0.72 if signature.get("sample_count") else 0.0
        similarity = self.similarity(signature, previous_signature)
        return _clamp(1.0 - similarity)

    def _cluster_for_signature(self, signature: Dict[str, Any], cluster_centers: List[Dict[str, Any]]) -> str:
        if not signature.get("sample_count"):
            return "unknown"
        for index, center in enumerate(cluster_centers, start=1):
            if self.similarity(signature, center) >= 0.86:
                return f"cluster_{index}"
        cluster_centers.append(signature)
        return f"cluster_{len(cluster_centers)}"

    def _hist_distance(self, left_hist: Sequence[float], right_hist: Sequence[float]) -> float:
        if not left_hist or not right_hist or len(left_hist) != len(right_hist):
            return 1.0
        return min(
            sum(abs(float(left_hist[idx]) - float(right_hist[idx])) for idx in range(len(left_hist))) / 2.0,
            1.0,
        )

    def _hash_distance(self, left_hash: str, right_hash: str) -> float:
        if not left_hash or not right_hash or len(left_hash) != len(right_hash):
            return 1.0
        mismatches = sum(1 for left_bit, right_bit in zip(left_hash, right_hash) if left_bit != right_bit)
        return mismatches / max(len(left_hash), 1)

    def _empty_signature(self) -> Dict[str, Any]:
        return {
            "sample_count": 0,
            "brightness": 0.0,
            "contrast": 0.0,
            "edge_density": 0.0,
            "mean_bgr": [0.0, 0.0, 0.0],
            "color_histogram": [0.0] * 12,
            "ahash": "",
            "dominant_channel": "unknown",
        }
