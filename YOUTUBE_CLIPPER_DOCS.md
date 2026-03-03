# YouTube Video Clipper Tool - Documentation

A powerful tool that clips YouTube videos based on timestamps and automatically uploads them to Google Drive.

## Features

✅ **Download YouTube videos** - Uses yt-dlp to download videos from YouTube  
✅ **Clip videos precisely** - Extract segments based on start/end timestamps  
✅ **Auto-upload to Google Drive** - Seamlessly upload clips to a specified folder  
✅ **Batch processing** - Process multiple clips in one request  
✅ **Multiple time formats** - Support for seconds, MM:SS, or HH:MM:SS formats  
✅ **Built-in error handling** - Comprehensive error messages and cleanup  

---

## Installation

### 1. Install Dependencies

The following packages are already added to `requirements.txt`:

```bash
pip install -r requirements.txt
```

Key packages needed:
- **yt-dlp** - YouTube video downloader
- **ffmpeg-python** - Video processing library
- **google-api-python-client** - Google Drive integration

### 2. System Requirements

You need **FFmpeg** installed on your system:

**Windows (using Chocolatey):**
```powershell
choco install ffmpeg
```

**Windows (manual installation):**
- Download from: https://ffmpeg.org/download.html
- Add FFmpeg to your system PATH

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install ffmpeg
```

### 3. Google Drive Setup

The tool uses your existing Google Drive service account. Ensure:
- `service-account.json` exists in the project root
- The service account has access to the target Google Drive folder
- The folder ID is correct (default: `1Kdu-CDI670WegvpFiK2ypPDtoqvlO0K8`)

---

## API Endpoints

### 1. Single Clip Endpoint

**Endpoint:** `POST /youtube-clip`

**Description:** Clip a single YouTube video and upload to Google Drive.

**Request Body:**
```json
{
  "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "start_time": "1:30",
  "end_time": "3:45",
  "clip_name": "my_awesome_clip.mp4",
  "output_folder_id": "1Kdu-CDI670WegvpFiK2ypPDtoqvlO0K8"
}
```

**Time Format Options:**
- `"90"` - Seconds as string or number
- `"1:30"` - MM:SS format
- `"0:01:30"` - HH:MM:SS format

**Response (Success):**
```json
{
  "success": true,
  "file_id": "1abc123xyz...",
  "file_name": "my_awesome_clip.mp4",
  "drive_link": "https://drive.google.com/file/d/1abc123xyz.../view",
  "clip_info": {
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "start_time": 90,
    "end_time": 225,
    "duration": 135
  }
}
```

**Response (Error):**
```json
{
  "success": false,
  "error": "Failed to download video"
}
```

---

### 2. Batch Clips Endpoint

**Endpoint:** `POST /youtube-clip-batch`

**Description:** Clip multiple YouTube videos in a single request.

**Request Body:**
```json
{
  "clips": [
    {
      "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      "start_time": "1:30",
      "end_time": "3:45",
      "name": "clip1.mp4"
    },
    {
      "url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
      "start_time": "0:20",
      "end_time": "1:45",
      "name": "clip2.mp4"
    }
  ],
  "output_folder_id": "1Kdu-CDI670WegvpFiK2ypPDtoqvlO0K8"
}
```

**Response:**
```json
{
  "total": 2,
  "successful": 2,
  "failed": 0,
  "clips": [
    {
      "success": true,
      "file_id": "1abc123xyz...",
      "file_name": "clip1.mp4",
      "drive_link": "https://drive.google.com/file/d/1abc123xyz.../view",
      "clip_info": {
        "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "start_time": 90,
        "end_time": 225,
        "duration": 135
      }
    },
    {
      "success": true,
      "file_id": "2def456uvw...",
      "file_name": "clip2.mp4",
      "drive_link": "https://drive.google.com/file/d/2def456uvw.../view",
      "clip_info": {
        "youtube_url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
        "start_time": 20,
        "end_time": 105,
        "duration": 85
      }
    }
  ]
}
```

---

## Usage Examples

### Using cURL

**Single Clip:**
```bash
curl -X POST "http://localhost:8000/youtube-clip" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "start_time": "1:30",
    "end_time": "3:45",
    "clip_name": "my_clip.mp4"
  }'
```

**Batch Clips:**
```bash
curl -X POST "http://localhost:8000/youtube-clip-batch" \
  -H "Content-Type: application/json" \
  -d '{
    "clips": [
      {
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "start_time": "1:30",
        "end_time": "3:45"
      },
      {
        "url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
        "start_time": "20",
        "end_time": "105"
      }
    ]
  }'
```

### Using Python

```python
import requests

# Single clip
response = requests.post(
    "http://localhost:8000/youtube-clip",
    json={
        "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "start_time": "1:30",
        "end_time": "3:45",
        "clip_name": "my_clip.mp4"
    }
)
print(response.json())

# Batch clips
response = requests.post(
    "http://localhost:8000/youtube-clip-batch",
    json={
        "clips": [
            {
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "start_time": "1:30",
                "end_time": "3:45",
                "name": "clip1.mp4"
            },
            {
                "url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
                "start_time": "0:20",
                "end_time": "1:45",
                "name": "clip2.mp4"
            }
        ]
    }
)
print(response.json())
```

### Using JavaScript/Fetch

```javascript
// Single clip
const response = await fetch('http://localhost:8000/youtube-clip', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    youtube_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    start_time: '1:30',
    end_time: '3:45',
    clip_name: 'my_clip.mp4'
  })
});
const result = await response.json();
console.log(result);
```

---

## How It Works

### Process Flow

1. **Download** - Uses yt-dlp to download the YouTube video
2. **Clip** - Uses ffmpeg to extract the specified time segment
3. **Upload** - Uploads the clipped video to Google Drive
4. **Cleanup** - Removes temporary files automatically

### Architecture

```
YouTubeClipper Class
├── __init__()                      - Initialize with Google Drive credentials
├── download_video()                - Download video using yt-dlp
├── clip_video()                    - Clip video using ffmpeg
├── upload_to_drive()               - Upload to Google Drive
├── process_youtube_clip()          - Single clip workflow
└── process_batch_clips()           - Batch clip workflow
```

---

## Troubleshooting

### Issue: "yt-dlp not found"

**Solution:**
```bash
pip install yt-dlp
```

### Issue: "ffmpeg not found"

**Solution:**

Make sure FFmpeg is installed and in your PATH:

```bash
# Check if FFmpeg is installed
ffmpeg -version

# If not, install it based on your OS (see Installation section)
```

### Issue: "Failed to authenticate with Google Drive"

**Solution:**
1. Verify `service-account.json` exists
2. Check that the service account has the correct scopes
3. Ensure the service account has access to the target Google Drive folder

### Issue: "Invalid time format"

**Solution:**
Use one of these formats:
- `"90"` - seconds
- `"1:30"` - MM:SS
- `"0:01:30"` - HH:MM:SS

### Issue: Video doesn't clip correctly

**Solution:**
- Verify start_time < end_time
- Check that the times are within the video duration
- Try using an absolute timestamp format (HH:MM:SS)

---

## Performance Tips

1. **Batch Processing** - Use batch endpoint for multiple clips to process them sequentially
2. **Time Limits** - Keep clips under 15 minutes for faster processing
3. **File Format** - Output is automatically MP4 with H.264 codec (widely compatible)

---

## Default Configuration

- **Default Output Folder ID:** `1Kdu-CDI670WegvpFiK2ypPDtoqvlO0K8`
- **Video Codec:** H.264 (libx264)
- **Audio Codec:** AAC
- **Output Format:** MP4
- **Temporary Directory:** System temp folder

---

## Security Notes

- Never expose your `service-account.json` file publicly
- Validate and sanitize YouTube URLs before processing
- Implement rate limiting in your frontend
- Consider adding authentication to the API endpoints

---

## Integration with Existing AI-Editor

The YouTube Clipper integrates seamlessly with your existing AI-Editor pipeline:

```python
from ai_editor.youtube_clipper import YouTubeClipper

clipper = YouTubeClipper()
result = clipper.process_youtube_clip(
    yt_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    start_time="1:30",
    end_time="3:45",
    output_folder_id="1Kdu-CDI670WegvpFiK2ypPDtoqvlO0K8"
)

if result["success"]:
    print(f"Uploaded: {result['drive_link']}")
```

---

## API Documentation

When running the FastAPI server, you can access the interactive API documentation at:

- **Swagger UI:** `http://localhost:8000/api/docs`
- **ReDoc:** `http://localhost:8000/api/redoc`

Both interfaces allow you to test the endpoints directly!

---

## Future Enhancements

- [ ] Support for playlist clipping
- [ ] Video quality selection
- [ ] Custom output codec options
- [ ] Thumbnail generation
- [ ] Webhook notifications
- [ ] Progress tracking for long videos
- [ ] Automatic video format conversion

---

## License & Attribution

This tool is part of the AI-Editor project.

For issues or questions, refer to the main project documentation.
