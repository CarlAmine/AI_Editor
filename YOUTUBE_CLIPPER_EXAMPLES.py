"""
YOUTUBE CLIPPER - QUICK REFERENCE GUIDE
========================================

This file contains practical examples for using the YouTube Clipper tool.
"""

# ============================================================================
# EXAMPLE 1: Direct Python Usage
# ============================================================================

from ai_editor.youtube_clipper import YouTubeClipper

# Initialize the clipper
clipper = YouTubeClipper()

# Single video clip
result = clipper.process_youtube_clip(
    yt_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    start_time="1:30",           # MM:SS format
    end_time="3:45",             # MM:SS format
    output_folder_id="1Kdu-CDI670WegvpFiK2ypPDtoqvlO0K8",
    clip_name="amazing_clip.mp4"
)

if result["success"]:
    print(f"✅ Clip uploaded! Drive link: {result['drive_link']}")
    print(f"Duration: {result['clip_info']['duration']} seconds")
else:
    print(f"❌ Error: {result['error']}")


# ============================================================================
# EXAMPLE 2: Batch Processing Multiple Videos
# ============================================================================

clips_to_process = [
    {
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "start_time": "00:30",          # HH:MM:SS format
        "end_time": "02:15",            # HH:MM:SS format
        "name": "intro_section.mp4"
    },
    {
        "url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
        "start_time": "5:00",           # MM:SS format
        "end_time": "7:30",
        "name": "main_content.mp4"
    },
    {
        "url": "https://www.youtube.com/watch?v=another_video_id",
        "start_time": "120",            # Seconds as string
        "end_time": "300",
        # name is optional - will be auto-generated
    }
]

batch_result = clipper.process_batch_clips(
    clips_data=clips_to_process,
    output_folder_id="1Kdu-CDI670WegvpFiK2ypPDtoqvlO0K8"
)

print(f"\n📊 Batch Processing Results:")
print(f"Total: {batch_result['total']}")
print(f"Successful: {batch_result['successful']}")
print(f"Failed: {batch_result['failed']}")

for i, clip_result in enumerate(batch_result['clips'], 1):
    if clip_result['success']:
        print(f"\n  ✅ Clip {i}: {clip_result['file_name']}")
        print(f"     Duration: {clip_result['clip_info']['duration']}s")
        print(f"     Link: {clip_result['drive_link']}")
    else:
        print(f"\n  ❌ Clip {i}: {clip_result['error']}")


# ============================================================================
# EXAMPLE 3: Using the REST API with Python requests
# ============================================================================

import requests
import json

BASE_URL = "http://localhost:8000"

# Single Clip REST API Call
single_clip_payload = {
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "start_time": "1:30",
    "end_time": "3:45",
    "clip_name": "my_api_clip.mp4",
    "output_folder_id": "1Kdu-CDI670WegvpFiK2ypPDtoqvlO0K8"
}

response = requests.post(
    f"{BASE_URL}/youtube-clip",
    json=single_clip_payload
)

result = response.json()
print("\n🌐 REST API Response:")
print(json.dumps(result, indent=2))


# Batch Clips REST API Call
batch_payload = {
    "clips": [
        {
            "url": "https://www.youtube.com/watch?v=video1",
            "start_time": "1:00",
            "end_time": "2:30",
            "name": "cut1.mp4"
        },
        {
            "url": "https://www.youtube.com/watch?v=video2",
            "start_time": "0:45",
            "end_time": "1:20",
            "name": "cut2.mp4"
        }
    ],
    "output_folder_id": "1Kdu-CDI670WegvpFiK2ypPDtoqvlO0K8"
}

response = requests.post(
    f"{BASE_URL}/youtube-clip-batch",
    json=batch_payload
)

batch_result = response.json()
print("\n📦 Batch REST API Response:")
print(json.dumps(batch_result, indent=2))


# ============================================================================
# EXAMPLE 4: Using cURL from Command Line
# ============================================================================

"""
# Single clip with cURL:
curl -X POST "http://localhost:8000/youtube-clip" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "start_time": "1:30",
    "end_time": "3:45",
    "clip_name": "my_clip.mp4"
  }'

# Batch clips with cURL:
curl -X POST "http://localhost:8000/youtube-clip-batch" \
  -H "Content-Type: application/json" \
  -d '{
    "clips": [
      {
        "url": "https://www.youtube.com/watch?v=video1",
        "start_time": "1:00",
        "end_time": "2:30"
      },
      {
        "url": "https://www.youtube.com/watch?v=video2",
        "start_time": "0:45",
        "end_time": "1:20"
      }
    ]
  }'
"""


# ============================================================================
# EXAMPLE 5: JavaScript/Frontend Integration
# ============================================================================

"""
// Fetch API for single clip
async function clipYouTubeVideo() {
  const response = await fetch('/youtube-clip', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      youtube_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
      start_time: '1:30',
      end_time: '3:45',
      clip_name: 'awesome_clip.mp4'
    })
  });
  
  const result = await response.json();
  
  if (result.success) {
    console.log('✅ Clip uploaded!');
    console.log('Drive link:', result.drive_link);
    console.log('Duration:', result.clip_info.duration, 'seconds');
  } else {
    console.error('❌ Error:', result.error);
  }
}

// Batch processing with progress tracking
async function clipMultipleVideos(clipsList) {
  const response = await fetch('/youtube-clip-batch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      clips: clipsList,
      output_folder_id: '1Kdu-CDI670WegvpFiK2ypPDtoqvlO0K8'
    })
  });
  
  const result = await response.json();
  
  console.log(`📊 Results: ${result.successful}/${result.total} successful`);
  
  result.clips.forEach((clip, index) => {
    if (clip.success) {
      console.log(`✅ Clip ${index + 1}: ${clip.file_name}`);
    } else {
      console.log(`❌ Clip ${index + 1} failed: ${clip.error}`);
    }
  });
  
  return result;
}

// Usage
const clips = [
  { url: 'https://youtube.com/watch?v=...', start_time: '1:00', end_time: '2:30' },
  { url: 'https://youtube.com/watch?v=...', start_time: '0:45', end_time: '1:20' }
];

clipMultipleVideos(clips);
"""


# ============================================================================
# EXAMPLE 6: Time Format Examples
# ============================================================================

"""
All these formats are valid for start_time and end_time:

Seconds:
  - 90 (as number)
  - "90" (as string)

MM:SS format:
  - "1:30" (1 minute 30 seconds = 90 seconds)
  - "5:45" (5 minutes 45 seconds = 345 seconds)

HH:MM:SS format:
  - "0:01:30" (1 minute 30 seconds = 90 seconds)
  - "1:05:30" (1 hour 5 minutes 30 seconds)
  - "0:00:45" (45 seconds)
"""


# ============================================================================
# EXAMPLE 7: Error Handling Best Practices
# ============================================================================

def safe_clip_video(yt_url, start, end, folder_id, max_retries=3):
    """
    Safely clip a video with retry logic and comprehensive error handling.
    """
    clipper = YouTubeClipper()
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Attempting clip (try {attempt}/{max_retries})...")
            
            result = clipper.process_youtube_clip(
                yt_url=yt_url,
                start_time=start,
                end_time=end,
                output_folder_id=folder_id
            )
            
            if result["success"]:
                print(f"✅ Success! File uploaded: {result['file_name']}")
                return result
            else:
                error_msg = result.get("error", "Unknown error")
                print(f"⚠️  Attempt {attempt} failed: {error_msg}")
                
                # Check for specific error types
                if "download" in error_msg.lower():
                    print("   → Check YouTube URL validity")
                elif "ffmpeg" in error_msg.lower():
                    print("   → FFmpeg might not be installed")
                elif "google" in error_msg.lower():
                    print("   → Google Drive authentication issue")
                elif "time" in error_msg.lower():
                    print("   → Check timestamp validity")
                
        except Exception as e:
            print(f"❌ Exception on attempt {attempt}: {str(e)}")
            
            if attempt == max_retries:
                return {
                    "success": False,
                    "error": f"Failed after {max_retries} attempts: {str(e)}"
                }
    
    return {
        "success": False,
        "error": f"Failed after {max_retries} attempts"
    }


# Usage:
result = safe_clip_video(
    yt_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    start="1:30",
    end="3:45",
    folder_id="1Kdu-CDI670WegvpFiK2ypPDtoqvlO0K8"
)


# ============================================================================
# EXAMPLE 8: Integration with Frontend UI Component (React/TypeScript)
# ============================================================================

"""
import React, { useState } from 'react';

interface Clip {
  url: string;
  start_time: string;
  end_time: string;
  name?: string;
}

export const YouTubeClipper: React.FC = () => {
  const [clips, setClips] = useState<Clip[]>([]);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);

  const handleClipVideo = async () => {
    setLoading(true);
    try {
      const response = await fetch('/youtube-clip-batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          clips: clips,
          output_folder_id: '1Kdu-CDI670WegvpFiK2ypPDtoqvlO0K8'
        })
      });
      
      const data = await response.json();
      setResults(data);
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      {/* UI for adding clips */}
      <button 
        onClick={handleClipVideo} 
        disabled={loading || clips.length === 0}
      >
        {loading ? 'Processing...' : 'Clip Videos'}
      </button>
      
      {results && (
        <div>
          <p>Success: {results.successful}/{results.total}</p>
          {results.clips.map((clip, idx) => (
            <div key={idx}>
              {clip.success ? (
                <a href={clip.drive_link} target="_blank">
                  ✅ {clip.file_name}
                </a>
              ) : (
                <span>❌ {clip.error}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
"""


# ============================================================================
# COMMON RECIPES
# ============================================================================

"""
RECIPE 1: Clip Every 30 Seconds from a Video
---
clips = [
    {"url": "video_url", "start_time": str(i), "end_time": str(i+30)}
    for i in range(0, 600, 30)  # 10 minute video
]

RECIPE 2: Extract Multiple Highlights
---
highlights = [
    {"url": "video_url", "start_time": "0:15", "end_time": "1:00"},   # Intro
    {"url": "video_url", "start_time": "5:30", "end_time": "7:45"},   # Main point
    {"url": "video_url", "start_time": "15:00", "end_time": "16:30"}, # Conclusion
]

RECIPE 3: Process Same Video Multiple Times with Different Cuts
---
same_video = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
clips = [
    {"url": same_video, "start_time": "0:00", "end_time": "2:00", "name": "part1.mp4"},
    {"url": same_video, "start_time": "2:00", "end_time": "4:00", "name": "part2.mp4"},
    {"url": same_video, "start_time": "4:00", "end_time": "6:00", "name": "part3.mp4"},
]
"""

# ============================================================================
# END OF QUICK REFERENCE
# ============================================================================
