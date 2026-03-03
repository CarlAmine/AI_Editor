#!/usr/bin/env python3
"""
YouTube Clipper - Standalone Test Script

This script allows you to test the YouTube Clipper functionality directly
without needing to run the FastAPI server.

Usage:
    python youtube_clipper_test.py

Or with arguments:
    python youtube_clipper_test.py --url "https://youtube.com/..." --start "1:30" --end "3:45"
"""

import argparse
import sys
import json
from pathlib import Path

# Add parent directory to path to import ai_editor module
sys.path.insert(0, str(Path(__file__).parent))

from ai_editor.youtube_clipper import YouTubeClipper


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(result):
    """Pretty print the result."""
    print(json.dumps(result, indent=2))


def test_single_clip():
    """Test single video clipping."""
    print_section("TEST 1: Single Video Clip")
    
    print("\nInitializing YouTube Clipper...")
    clipper = YouTubeClipper()
    
    # Example video URL (Rick Roll - famous short video)
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    start_time = "1:30"
    end_time = "3:45"
    
    print(f"\nClipping video:")
    print(f"  URL: {test_url}")
    print(f"  Start: {start_time}")
    print(f"  End: {end_time}")
    print("\nProcessing (this may take a minute)...\n")
    
    result = clipper.process_youtube_clip(
        yt_url=test_url,
        start_time=start_time,
        end_time=end_time,
        output_folder_id="1Kdu-CDI670WegvpFiK2ypPDtoqvlO0K8",
        clip_name="test_single_clip.mp4"
    )
    
    print("Result:")
    print_result(result)
    
    return result["success"]


def test_batch_clips():
    """Test batch video clipping."""
    print_section("TEST 2: Batch Video Clips")
    
    print("\nInitializing YouTube Clipper...")
    clipper = YouTubeClipper()
    
    clips_to_process = [
        {
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "start_time": "0:30",
            "end_time": "2:00",
            "name": "test_batch_clip1.mp4"
        },
        {
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "start_time": "2:00",
            "end_time": "3:30",
            "name": "test_batch_clip2.mp4"
        }
    ]
    
    print(f"\nClipping {len(clips_to_process)} videos...")
    for i, clip in enumerate(clips_to_process, 1):
        print(f"  {i}. {clip['name']}: {clip['start_time']} - {clip['end_time']}")
    
    print("\nProcessing (this may take a few minutes)...\n")
    
    result = clipper.process_batch_clips(
        clips_data=clips_to_process,
        output_folder_id="1Kdu-CDI670WegvpFiK2ypPDtoqvlO0K8",
    )
    
    print("Results:")
    print_result(result)
    
    return result["successful"] == len(clips_to_process)


def test_time_formats():
    """Test different timestamp formats (without actually downloading)."""
    print_section("TEST 3: Time Format Parsing")
    
    clipper = YouTubeClipper()
    
    test_cases = [
        ("90", 90, "Seconds as string"),
        (90, 90, "Seconds as number"),
        ("1:30", 90, "MM:SS format"),
        ("0:01:30", 90, "HH:MM:SS format"),
        ("5:45", 345, "MM:SS format (5:45)"),
        ("0:05:45", 345, "HH:MM:SS format (5:45)"),
        ("1:02:30", 3750, "HH:MM:SS format (1h 2m 30s)"),
    ]
    
    print("\nTesting timestamp parsing:\n")
    all_passed = True
    
    for input_val, expected, description in test_cases:
        parsed = clipper._parse_timestamp(input_val)
        status = "✅ PASS" if parsed == expected else "❌ FAIL"
        
        if parsed != expected:
            all_passed = False
        
        print(f"{status} | {description}")
        print(f"      Input: {input_val!r} → Output: {parsed}s (Expected: {expected}s)")
    
    return all_passed


def test_custom_clip(url, start, end, folder_id=None):
    """Test clipping with user-provided parameters."""
    print_section("CUSTOM CLIP TEST")
    
    if not folder_id:
        folder_id = "1Kdu-CDI670WegvpFiK2ypPDtoqvlO0K8"
    
    print(f"\nClipping custom video:")
    print(f"  URL: {url}")
    print(f"  Start: {start}")
    print(f"  End: {end}")
    print(f"  Folder ID: {folder_id}")
    print("\nProcessing (this may take a minute)...\n")
    
    clipper = YouTubeClipper()
    result = clipper.process_youtube_clip(
        yt_url=url,
        start_time=start,
        end_time=end,
        output_folder_id=folder_id,
        clip_name="custom_test_clip.mp4"
    )
    
    print("Result:")
    print_result(result)
    
    return result["success"]


def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(
        description="YouTube Clipper Test Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run default tests
  python youtube_clipper_test.py
  
  # Test with custom video
  python youtube_clipper_test.py --url "https://youtube.com/watch?v=..." \\
                                  --start "1:30" --end "3:45"
  
  # Test with different folder
  python youtube_clipper_test.py --folder "YOUR_FOLDER_ID"
        """
    )
    
    parser.add_argument(
        "--url",
        type=str,
        help="YouTube URL to test with"
    )
    parser.add_argument(
        "--start",
        type=str,
        default="1:30",
        help="Start time (default: 1:30)"
    )
    parser.add_argument(
        "--end",
        type=str,
        default="3:45",
        help="End time (default: 3:45)"
    )
    parser.add_argument(
        "--folder",
        type=str,
        help="Google Drive folder ID (optional)"
    )
    parser.add_argument(
        "--test",
        type=str,
        choices=["single", "batch", "time", "all"],
        default="all",
        help="Which test to run (default: all)"
    )
    parser.add_argument(
        "--skip-downloads",
        action="store_true",
        help="Skip tests that require downloading videos"
    )
    
    args = parser.parse_args()
    
    print("\n" + "🎬" * 30)
    print("\n   YOUTUBE CLIPPER - TEST SUITE")
    print("\n" + "🎬" * 30)
    
    results = {}
    
    try:
        # Test 1: Time format parsing (no downloads needed)
        if args.test in ["time", "all"]:
            results["time_format"] = test_time_formats()
        
        # If user provided custom URL, test with that
        if args.url:
            results["custom"] = test_custom_clip(
                args.url,
                args.start,
                args.end,
                args.folder
            )
        
        # Skip download tests if requested
        elif not args.skip_downloads:
            if args.test in ["single", "all"]:
                results["single"] = test_single_clip()
            
            if args.test in ["batch", "all"]:
                results["batch"] = test_batch_clips()
        
        # Summary
        print_section("TEST SUMMARY")
        print()
        for test_name, passed in results.items():
            status = "✅ PASSED" if passed else "❌ FAILED"
            print(f"  {test_name:20} : {status}")
        
        all_passed = all(results.values())
        
        print()
        if all_passed:
            print("  🎉 All tests passed!")
        else:
            print("  ⚠️  Some tests failed. Check the output above.")
        
        print()
        print("=" * 60)
        
        return 0 if all_passed else 1
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        return 2
    except Exception as e:
        print_section("ERROR")
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
