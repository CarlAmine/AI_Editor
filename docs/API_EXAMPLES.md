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

### Example 1: Basic Request
```python
import requests

API_BASE = "http://localhost:8000"

payload = {
    "primary_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "sources": [
        {
            "label": 1,
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "segments": None
        }
    ],
    "prompt": "Create an exciting 15-second clip",
    "music_mode": "original"
}

response = requests.post(f"{API_BASE}/process-video-url", json=payload)
result = response.json()

if result.get("success"):
    print(f"Video URL: {result.get('url')}")
else:
    print(f"Error: {result.get('error')}")
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
                timeout=300
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timeout (5 minutes)."}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Cannot connect to API. Is the backend running?"}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}
```

### Example 3: Batch Processing
```python
import requests, time
from typing import List, Dict

def process_batch(jobs: List[Dict], api_base: str = "http://localhost:8000") -> List[Dict]:
    results = []
    for i, job in enumerate(jobs, 1):
        print(f"[{i}/{len(jobs)}] Processing: {job.get('name', f'Job {i}')}")
        try:
            response = requests.post(f"{api_base}/process-video-url", json=job, timeout=300)
            result = response.json()
            result["job_name"] = job.get("name", f"Job {i}")
            results.append(result)
        except Exception as e:
            results.append({"success": False, "error": str(e), "job_name": job.get("name")})
        if i < len(jobs):
            time.sleep(2)
    return results
```

---

## Using JavaScript/TypeScript

### Basic Fetch
```javascript
const response = await fetch("http://localhost:8000/process-video-url", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    primary_url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    sources: [{ label: 1, url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ", segments: null }],
    prompt: "Create a fun 15-second clip",
    music_mode: "original",
    requirements_state: {}
  })
});

const result = await response.json();
if (result.success) console.log("Video:", result.url);
```

---

## Response Format

### Success
```json
{
  "success": true,
  "url": "https://shotstack-api.s3.amazonaws.com/renders/abc123.mp4",
  "render_id": "abc123def456"
}
```

### Error
```json
{
  "success": false,
  "error": "Failed to download primary video: Video unavailable or private"
}
```

---

## Segment Format Reference

```json
"segments": null                            // Whole video
"segments": [{"start": 10, "end": 30}]     // Single clip
"segments": [{"start": 0, "end": 15}, {"start": 30, "end": 45}]  // Multi-clip
```

---

**Last Updated:** March 2026 | **API Version:** 1.0
