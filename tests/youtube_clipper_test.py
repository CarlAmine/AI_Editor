#!/usr/bin/env python3
"""
YouTube Clipper - Test Script

Usage:
    python tests/youtube_clipper_test.py
    python tests/youtube_clipper_test.py --url "https://youtube.com/..." --start "1:30" --end "3:45"
    python tests/youtube_clipper_test.py --test time   # Only run time-format tests (no downloads)
    python tests/youtube_clipper_test.py --skip-downloads
"""

import argparse
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_editor.youtube_clipper import YouTubeClipper


def print_section(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_time_formats():
    """Test timestamp parsing without downloading anything."""
    print_section("Time Format Parsing")
    clipper = YouTubeClipper()
    test_cases = [
        ("90", 90, "Seconds as string"),
        (90, 90, "Seconds as number"),
        ("1:30", 90, "MM:SS format"),
        ("0:01:30", 90, "HH:MM:SS format"),
        ("5:45", 345, "MM:SS (5:45)"),
        ("1:02:30", 3750, "HH:MM:SS (1h 2m 30s)"),
    ]
    all_passed = True
    for input_val, expected, description in test_cases:
        parsed = clipper._parse_timestamp(input_val)
        passed = parsed == expected
        if not passed:
            all_passed = False
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} | {description}: {input_val!r} → {parsed}s (expected {expected}s)")
    return all_passed


def test_single_clip():
    print_section("Single Video Clip")
    clipper = YouTubeClipper()
    result = clipper.process_youtube_clip(
        yt_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        start_time="1:30",
        end_time="3:45",
        output_folder_id="1Kdu-CDI670WegvpFiK2ypPDtoqvlO0K8",
        clip_name="test_single_clip.mp4"
    )
    print(json.dumps(result, indent=2))
    return result["success"]


def test_batch_clips():
    print_section("Batch Video Clips")
    clipper = YouTubeClipper()
    clips = [
        {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "start_time": "0:30", "end_time": "2:00", "name": "batch1.mp4"},
        {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "start_time": "2:00", "end_time": "3:30", "name": "batch2.mp4"},
    ]
    result = clipper.process_batch_clips(
        clips_data=clips,
        output_folder_id="1Kdu-CDI670WegvpFiK2ypPDtoqvlO0K8",
    )
    print(json.dumps(result, indent=2))
    return result["successful"] == len(clips)


def main():
    parser = argparse.ArgumentParser(description="YouTube Clipper Test Script")
    parser.add_argument("--url", type=str)
    parser.add_argument("--start", type=str, default="1:30")
    parser.add_argument("--end", type=str, default="3:45")
    parser.add_argument("--test", choices=["single", "batch", "time", "all"], default="all")
    parser.add_argument("--skip-downloads", action="store_true")
    args = parser.parse_args()

    results = {}

    try:
        if args.test in ["time", "all"]:
            results["time_format"] = test_time_formats()

        if not args.skip_downloads and not args.url:
            if args.test in ["single", "all"]:
                results["single"] = test_single_clip()
            if args.test in ["batch", "all"]:
                results["batch"] = test_batch_clips()

        print_section("Summary")
        for name, passed in results.items():
            print(f"  {'✅ PASSED' if passed else '❌ FAILED'} : {name}")

        return 0 if all(results.values()) else 1

    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 2
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
