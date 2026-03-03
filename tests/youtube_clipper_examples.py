"""
YouTube Clipper - Usage Examples

Quick reference for direct Python, REST API, cURL, and JavaScript usage.
"""

# ============================================================================
# EXAMPLE 1: Direct Python Usage
# ============================================================================

from ai_editor.youtube_clipper import YouTubeClipper

clipper = YouTubeClipper()

# Single clip
result = clipper.process_youtube_clip(
    yt_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    start_time="1:30",
    end_time="3:45",
    output_folder_id="YOUR_DRIVE_FOLDER_ID",
    clip_name="my_clip.mp4"
)

if result["success"]:
    print(f"Uploaded: {result['drive_link']}")
else:
    print(f"Error: {result['error']}")


# ============================================================================
# EXAMPLE 2: Batch Processing
# ============================================================================

clips = [
    {"url": "https://youtube.com/watch?v=abc", "start_time": "0:30", "end_time": "2:00", "name": "intro.mp4"},
    {"url": "https://youtube.com/watch?v=def", "start_time": "5:00", "end_time": "7:30", "name": "main.mp4"},
]

batch_result = clipper.process_batch_clips(clips_data=clips, output_folder_id="YOUR_DRIVE_FOLDER_ID")
print(f"Successful: {batch_result['successful']}/{batch_result['total']}")


# ============================================================================
# EXAMPLE 3: REST API
# ============================================================================

import requests

# Single clip
response = requests.post("http://localhost:8000/youtube-clip", json={
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "start_time": "1:30",
    "end_time": "3:45",
    "clip_name": "my_clip.mp4",
    "output_folder_id": "YOUR_DRIVE_FOLDER_ID"
})
print(response.json())

# Batch clips
response = requests.post("http://localhost:8000/youtube-clip-batch", json={
    "clips": [
        {"url": "https://youtube.com/watch?v=abc", "start_time": "1:00", "end_time": "2:30", "name": "clip1.mp4"},
        {"url": "https://youtube.com/watch?v=def", "start_time": "0:45", "end_time": "1:20", "name": "clip2.mp4"},
    ],
    "output_folder_id": "YOUR_DRIVE_FOLDER_ID"
})
print(response.json())


# ============================================================================
# TIME FORMAT REFERENCE
# ============================================================================

"""
All accepted formats for start_time / end_time:

  90          → 90 seconds
  "90"        → 90 seconds
  "1:30"      → MM:SS = 90 seconds
  "0:01:30"   → HH:MM:SS = 90 seconds
  "1:02:30"   → 1h 2m 30s = 3750 seconds
"""
