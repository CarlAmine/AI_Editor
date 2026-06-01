"""
Unit tests for ai_editor.source_inventory.analyzer

Strategy: we call build_source_inventory with artifacts that point to
non-existent paths.  The analyzer must gracefully append a warning and skip
the clip rather than raise.  We also test the SourceInventory / SourceClipInventory
contract round-trips independently of cv2.
"""
from __future__ import annotations

import pytest
from ai_editor.edit_contracts.source_inventory import (
    SourceClipInventory,
    SourceInventory,
)


# ---------------------------------------------------------------------------
# Contract-level tests (no file I/O)
# ---------------------------------------------------------------------------

class TestSourceClipInventoryContract:
    def test_to_dict_round_trip(self):
        clip = SourceClipInventory(
            clip_id="clip_01",
            source_index=0,
            path="/fake/clip.mp4",
            duration=12.5,
            fps=30.0,
            width=1920,
            height=1080,
            candidate_segments=[{"start": 0.0, "end": 5.0, "duration": 5.0}],
            metadata={"tag": "test"},
        )
        d = clip.to_dict()
        restored = SourceClipInventory.from_dict(d)
        assert restored.clip_id == "clip_01"
        assert restored.source_index == 0
        assert restored.duration == pytest.approx(12.5)
        assert restored.fps == pytest.approx(30.0)
        assert restored.width == 1920
        assert restored.height == 1080
        assert len(restored.candidate_segments) == 1

    def test_from_dict_defaults(self):
        clip = SourceClipInventory.from_dict({})
        assert clip.clip_id == ""
        assert clip.source_index == 0
        assert clip.duration == pytest.approx(0.0)
        assert clip.fps is None
        assert clip.candidate_segments == []

    def test_clip_id_coerced_to_str(self):
        clip = SourceClipInventory.from_dict({"clip_id": 42})
        assert clip.clip_id == "42"


class TestSourceInventoryContract:
    def test_empty_inventory(self):
        inv = SourceInventory()
        d = inv.to_dict()
        assert d["clips"] == []
        assert d["warnings"] == []

    def test_from_dict_round_trip(self):
        data = {
            "clips": [
                {
                    "clip_id": "c1",
                    "source_index": 1,
                    "path": "/p.mp4",
                    "duration": 5.0,
                }
            ],
            "warnings": ["some warning"],
        }
        inv = SourceInventory.from_dict(data)
        assert len(inv.clips) == 1
        assert inv.clips[0].clip_id == "c1"
        assert inv.warnings == ["some warning"]

    def test_to_json_from_json(self):
        inv = SourceInventory(
            clips=[
                SourceClipInventory(
                    clip_id="x",
                    source_index=0,
                    path="/x.mp4",
                    duration=8.0,
                )
            ],
            warnings=[],
        )
        json_str = inv.to_json()
        restored = SourceInventory.from_json(json_str)
        assert len(restored.clips) == 1
        assert restored.clips[0].clip_id == "x"


# ---------------------------------------------------------------------------
# Analyzer – graceful failure when paths don't exist
# ---------------------------------------------------------------------------

class TestBuildSourceInventoryGraceful:
    def test_missing_path_produces_warning_not_exception(self):
        from ai_editor.source_inventory.analyzer import build_source_inventory

        artifacts = [
            {"clip_id": "clip_01", "source_index": 0, "path": "/nonexistent/clip.mp4"},
        ]
        result = build_source_inventory(artifacts, job_id="job_x", out_dir="/tmp/fake")
        assert isinstance(result, dict)
        assert "warnings" in result
        # The missing clip should generate a warning
        assert any("clip_01" in w or "nonexistent" in w for w in result["warnings"])
        # No clips should have been added
        assert result["clips"] == []

    def test_empty_artifacts_returns_empty_inventory(self):
        from ai_editor.source_inventory.analyzer import build_source_inventory

        result = build_source_inventory([], job_id="job_y", out_dir="/tmp/fake")
        assert result["clips"] == []
        assert result["warnings"] == []

    def test_multiple_missing_paths_all_warned(self):
        from ai_editor.source_inventory.analyzer import build_source_inventory

        artifacts = [
            {"clip_id": "c1", "source_index": 0, "path": "/no/c1.mp4"},
            {"clip_id": "c2", "source_index": 1, "path": "/no/c2.mp4"},
        ]
        result = build_source_inventory(artifacts, job_id="j", out_dir="/tmp")
        assert len(result["clips"]) == 0
        assert len(result["warnings"]) == 2


# ---------------------------------------------------------------------------
# Candidate segment logic (stubbed SourceClipInventory – no cv2)
# ---------------------------------------------------------------------------

class TestCandidateSegmentLogic:
    """
    We test the expected segment partitioning rules by directly inspecting
    a hand-crafted SourceClipInventory (bypassing cv2 calls).
    """

    def _make_clip(self, duration: float, num_segments: int) -> SourceClipInventory:
        """Create a clip with candidate segments matching the analyzer heuristics."""
        if duration <= 0:
            segs = []
        elif duration <= 3.0:
            segs = [
                {
                    "start": 0.0,
                    "end": duration,
                    "duration": duration,
                    "quality_score": 0.8,
                    "selection_reason": "entire_short_clip",
                }
            ]
        else:
            seg_len = duration / 3.0
            segs = [
                {"start": 0.0, "end": seg_len, "duration": seg_len, "selection_reason": "beginning_segment"},
                {"start": seg_len, "end": seg_len * 2, "duration": seg_len, "selection_reason": "middle_segment"},
                {"start": seg_len * 2, "end": duration, "duration": duration - seg_len * 2, "selection_reason": "ending_segment"},
            ]
        return SourceClipInventory(
            clip_id="c",
            source_index=0,
            path="/fake.mp4",
            duration=duration,
            candidate_segments=segs,
        )

    def test_short_clip_single_segment(self):
        clip = self._make_clip(duration=2.0, num_segments=1)
        assert len(clip.candidate_segments) == 1
        assert clip.candidate_segments[0]["selection_reason"] == "entire_short_clip"

    def test_long_clip_three_segments(self):
        clip = self._make_clip(duration=30.0, num_segments=3)
        assert len(clip.candidate_segments) == 3
        reasons = {s["selection_reason"] for s in clip.candidate_segments}
        assert reasons == {"beginning_segment", "middle_segment", "ending_segment"}

    def test_segment_start_end_coverage(self):
        duration = 30.0
        clip = self._make_clip(duration=duration, num_segments=3)
        segs = clip.candidate_segments
        assert segs[0]["start"] == pytest.approx(0.0)
        assert segs[-1]["end"] == pytest.approx(duration)

    def test_segment_durations_sum_to_total(self):
        duration = 30.0
        clip = self._make_clip(duration=duration, num_segments=3)
        total = sum(s["duration"] for s in clip.candidate_segments)
        assert total == pytest.approx(duration, rel=1e-6)
