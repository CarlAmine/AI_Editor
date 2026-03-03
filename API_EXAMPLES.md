# API Examples: /process-video-url Endpoint

## Using cURL

### Example 1: Single Video, No Clipping
```bash
curl -X POST http://localhost:8000/process-video-url \
  -H "Content-Type: application/json" \
  -d '{
    "primary_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "sources": [
      {
        "label": 1,
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
      }
    ],
    "prompt": "Make it snappy and engaging",
    "music_mode": "original"
  }'
```

### Example 2: Multiple Videos with Segments
```bash
curl -X POST http://localhost:8000/process-video-url \
  -H "Content-Type: application/json" \
  -d '{
    "primary_url": "https://www.youtube.com/watch?v=main_video",
    "sources": [
      {
        "label": 1,
        "url": "https://www.youtube.com/watch?v=intro",
        "segments": [
          {"start": 0, "end": 5},
          {"start": 10, "end": 15}
        ]
      },
      {
        "label": 2,
        "url": "https://www.youtube.com/watch?v=main",
        "segments": [
          {"start": 20, "end": 50}
        ]
      },
      {
        "label": 3,
        "url": "https://www.youtube.com/watch?v=outro",
        "segments": null
      }
    ],
    "prompt": "Create a fast-paced 30-second TikTok style edit",
    "music_mode": "custom",
    "custom_music_url": "https://www.youtube.com/watch?v=upbeat_music",
    "requirements_state": {
      "tone": "energetic",
      "pacing": "fast",
      "aspect_ratio": "9:16"
    }
  }'
```

---

## Using Python

### Example 1: Basic Request with yt-dlp and requests
```python
import requests
import json

API_BASE = "http://localhost:8000"

def process_video_basic():
    payload = {
        "primary_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "sources": [
            {
                "label": 1,
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "segments": None  # Use entire video
            }
        ],
        "prompt": "Create an exciting 15-second clip",
        "music_mode": "original"
    }
    
    response = requests.post(
        f"{API_BASE}/process-video-url",
        json=payload
    )
    
    result = response.json()
    
    if result.get("success"):
        print(f"✅ Success! Video: {result.get('url')}")
    else:
        print(f"❌ Error: {result.get('error')}")
    
    return result

# Run it
process_video_basic()
```

### Example 2: Advanced Request with Error Handling
```python
import requests
from typing import List, Dict, Optional

class VideoProcessor:
    def __init__(self, api_base: str = "http://localhost:8000"):
        self.api_base = api_base
    
    def process_videos(
        self,
        primary_url: str,
        sources: List[Dict],
        prompt: str,
        music_mode: str = "original",
        custom_music_url: Optional[str] = None,
        requirements_state: Optional[Dict] = None
    ) -> Dict:
        """Process videos via the API."""
        
        payload = {
            "primary_url": primary_url,
            "sources": sources,
            "prompt": prompt,
            "music_mode": music_mode,
            "custom_music_url": custom_music_url,
            "requirements_state": requirements_state or {}
        }
        
        try:
            response = requests.post(
                f"{self.api_base}/process-video-url",
                json=payload,
                timeout=300  # 5 minutes timeout
            )
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("success"):
                print(f"✅ Video rendered successfully")
                print(f"📺 URL: {result.get('url')}")
                return result
            else:
                print(f"❌ API Error: {result.get('error')}")
                return result
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Request timeout (5 minutes). The rendering may still be in progress."
            }
        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "error": "Cannot connect to API. Is the backend running?"
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"Request failed: {str(e)}"
            }

# Usage
processor = VideoProcessor()

# Simple example
result = processor.process_videos(
    primary_url="https://www.youtube.com/watch?v=video1",
    sources=[
        {
            "label": 1,
            "url": "https://www.youtube.com/watch?v=video1",
            "segments": [{"start": 10, "end": 30}]
        }
    ],
    prompt="Make it energetic"
)

# Complex example
result = processor.process_videos(
    primary_url="https://www.youtube.com/watch?v=highlight",
    sources=[
        {
            "label": 1,
            "url": "https://www.youtube.com/watch?v=clip1",
            "segments": [
                {"start": 5, "end": 15},
                {"start": 20, "end": 35}
            ]
        },
        {
            "label": 2,
            "url": "https://www.youtube.com/watch?v=clip2",
            "segments": [{"start": 0, "end": 10}]
        }
    ],
    prompt="30-second TikTok edit with bold captions",
    music_mode="custom",
    custom_music_url="https://www.youtube.com/watch?v=music",
    requirements_state={
        "tone": "energetic",
        "pacing": "fast",
        "aspect_ratio": "9:16"
    }
)
```

### Example 3: Batch Processing Multiple Jobs
```python
import requests
import time
from typing import List, Dict

class BatchVideoProcessor:
    def __init__(self, api_base: str = "http://localhost:8000"):
        self.api_base = api_base
    
    def process_batch(self, jobs: List[Dict]) -> List[Dict]:
        """Process multiple video jobs sequentially."""
        
        results = []
        
        for i, job in enumerate(jobs, 1):
            print(f"\n[{i}/{len(jobs)}] Processing: {job.get('name', f'Job {i}')}")
            print(f"  Primary URL: {job['primary_url'][:50]}...")
            print(f"  Sources: {len(job.get('sources', []))}")
            
            try:
                response = requests.post(
                    f"{self.api_base}/process-video-url",
                    json=job,
                    timeout=300
                )
                
                result = response.json()
                result["job_name"] = job.get("name", f"Job {i}")
                results.append(result)
                
                if result.get("success"):
                    print(f"  ✅ Success!")
                else:
                    print(f"  ❌ Failed: {result.get('error')}")
                
            except Exception as e:
                results.append({
                    "success": False,
                    "error": str(e),
                    "job_name": job.get("name", f"Job {i}")
                })
                print(f"  ❌ Exception: {str(e)}")
            
            # Small delay between requests
            if i < len(jobs):
                time.sleep(2)
        
        return results
    
    def print_summary(self, results: List[Dict]):
        """Print a summary of batch results."""
        
        successful = sum(1 for r in results if r.get("success"))
        failed = len(results) - successful
        
        print(f"\n{'='*60}")
        print(f"BATCH SUMMARY")
        print(f"{'='*60}")
        print(f"Total:      {len(results)}")
        print(f"Successful: {successful} ✅")
        print(f"Failed:     {failed} ❌")
        print(f"{'='*60}")
        
        print("\nDetails:")
        for result in results:
            status = "✅" if result.get("success") else "❌"
            name = result.get("job_name", "Unknown")
            if result.get("success"):
                print(f"  {status} {name}")
                print(f"     → {result.get('url')}")
            else:
                print(f"  {status} {name}")
                print(f"     → Error: {result.get('error')}")

# Example batch jobs
batch_jobs = [
    {
        "name": "30-sec TikTok Edit",
        "primary_url": "https://www.youtube.com/watch?v=video1",
        "sources": [
            {"label": 1, "url": "https://www.youtube.com/watch?v=video1", "segments": [{"start": 10, "end": 40}]}
        ],
        "prompt": "Fast-paced TikTok with captions",
        "music_mode": "original",
        "requirements_state": {"aspect_ratio": "9:16"}
    },
    {
        "name": "YouTube Highlight Reel",
        "primary_url": "https://www.youtube.com/watch?v=video2",
        "sources": [
            {"label": 1, "url": "https://www.youtube.com/watch?v=video2", "segments": [{"start": 0, "end": 60}]},
            {"label": 2, "url": "https://www.youtube.com/watch?v=video3", "segments": [{"start": 20, "end": 50}]}
        ],
        "prompt": "Epic highlight compilation",
        "music_mode": "custom",
        "custom_music_url": "https://www.youtube.com/watch?v=epic_music",
        "requirements_state": {"aspect_ratio": "16:9"}
    }
]

# Process batch
processor = BatchVideoProcessor()
results = processor.process_batch(batch_jobs)
processor.print_summary(results)
```

---

## Using JavaScript/Fetch

### Example 1: Basic Request
```javascript
async function processVideo() {
  const payload = {
    primary_url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    sources: [
      {
        label: 1,
        url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        segments: null
      }
    ],
    prompt: "Create a fun 15-second clip",
    music_mode: "original",
    requirements_state: {}
  };

  try {
    const response = await fetch("http://localhost:8000/process-video-url", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });

    const result = await response.json();

    if (result.success) {
      console.log("✅ Success!", result.url);
      return result;
    } else {
      console.log("❌ Error:", result.error);
      return result;
    }
  } catch (error) {
    console.error("Network error:", error);
    return { success: false, error: error.message };
  }
}

// Call it
processVideo();
```

### Example 2: React Hook with Status Updates
```typescript
import { useState } from "react";

interface VideoJob {
  primary_url: string;
  sources: Array<{
    label: number;
    url: string;
    segments?: Array<{ start: number; end: number }>;
  }>;
  prompt: string;
  music_mode: "original" | "custom";
  custom_music_url?: string;
}

export function useVideoProcessor() {
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const processVideo = async (job: VideoJob) => {
    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch("http://localhost:8000/process-video-url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(job)
      });

      const data = await response.json();
      setResult(data);

      if (!data.success) {
        setError(data.error || "Unknown error occurred");
      }

      return data;
    } catch (err: any) {
      const errorMsg = err?.message || "Network error";
      setError(errorMsg);
      return { success: false, error: errorMsg };
    } finally {
      setIsLoading(false);
    }
  };

  return { processVideo, isLoading, result, error };
}

// Usage in component
export function VideoEditor() {
  const { processVideo, isLoading, result, error } = useVideoProcessor();

  const handleSubmit = async (job: VideoJob) => {
    await processVideo(job);
  };

  return (
    <div>
      {isLoading && <p>Processing... This may take several minutes.</p>}
      {error && <p style={{ color: "red" }}>Error: {error}</p>}
      {result?.success && (
        <p>
          ✅ Done! <a href={result.url} target="_blank">View video</a>
        </p>
      )}
    </div>
  );
}
```

---

## Response Examples

### Success Response
```json
{
  "success": true,
  "url": "https://shotstack-api.s3.amazonaws.com/renders/abc123def456.mp4",
  "render_id": "abc123def456",
  "clip_info": {
    "total_clips": 3,
    "total_duration_seconds": 45.5
  }
}
```

### Error Response
```json
{
  "success": false,
  "error": "Failed to download primary video: Video unavailable or private"
}
```

---

## Common Segment Formats

All these are valid:

```json
// Whole video (no clipping)
"segments": null

// Single segment (seconds)
"segments": [{"start": 10, "end": 30}]

// Multiple segments
"segments": [
  {"start": 0, "end": 15},
  {"start": 30, "end": 45},
  {"start": 60, "end": 75}
]

// Overlapping is allowed (duplicates same parts)
"segments": [
  {"start": 10, "end": 30},
  {"start": 20, "end": 40}
]
```

---

## Testing the API

### Using Postman

1. Create new POST request
2. URL: `http://localhost:8000/process-video-url`
3. Headers: `Content-Type: application/json`
4. Body (raw JSON):
```json
{
  "primary_url": "https://www.youtube.com/watch?v=...",
  "sources": [{"label": 1, "url": "https://www.youtube.com/watch?v=...", "segments": null}],
  "prompt": "Test edit",
  "music_mode": "original"
}
```
5. Send and check response

### Using Swagger UI

1. Open: `http://localhost:8000/api/docs`
2. Find `/process-video-url` endpoint
3. Click "Try it out"
4. Fill in the example JSON
5. Click "Execute"

---

## Debugging

### Check logs for errors
```bash
# If running with --reload, check console output
python -m uvicorn app:app --reload

# Look for:
# [downloader] Downloading: ...
# ✓ Downloaded: ...
# [editor] Using ...
# ✓ Successfully created... clips
```

### Check temp directory
```bash
ls -la ./tmp/videos/
# Should be empty after successful render
# If not, clipping/rendering likely failed
```

### Test individual components
```bash
# Test download
python -c "from ai_editor.downloader import download_video; download_video('https://...', './tmp/test')"

# Test API directly
curl -X POST http://localhost:8000/process-video-url -H "Content-Type: application/json" -d '{...}'
```

---

**Last Updated:** March 2026  
**API Version:** 1.0
