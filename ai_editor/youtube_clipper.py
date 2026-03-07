"""
YouTube Video Clipper Tool
Handles downloading YouTube videos and clipping them based on timestamps,
then uploading the results to Google Drive.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Tuple
from dotenv import load_dotenv
from googleapiclient.http import MediaFileUpload

from .google_auth import build_drive_service, format_google_auth_error, GoogleCredentialError

load_dotenv()


class YouTubeClipper:
    """Handles YouTube video downloading and clipping operations."""

    def __init__(self):
        """Initialize the YouTube clipper with Google Drive credentials."""
        self.gdrive_service = self._get_drive_service()
        self.temp_dir = tempfile.gettempdir()

    @staticmethod
    def _get_drive_service():
        """Authenticates using the Service Account JSON file."""
        try:
            return build_drive_service(scopes=["https://www.googleapis.com/auth/drive"])
        except GoogleCredentialError:
            raise
        except Exception as e:
            raise GoogleCredentialError(format_google_auth_error(e)) from e

    @staticmethod
    def _parse_timestamp(timestamp_str: str) -> float:
        """
        Convert timestamp string to seconds.
        Supports formats: MM:SS, HH:MM:SS, or just seconds as number.
        """
        if isinstance(timestamp_str, (int, float)):
            return float(timestamp_str)

        parts = str(timestamp_str).split(":")
        if len(parts) == 2:  # MM:SS
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:  # HH:MM:SS
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        else:
            return float(timestamp_str)

    def download_video(self, yt_url: str, output_path: str) -> bool:
        """
        Download a YouTube video using yt-dlp.
        
        Args:
            yt_url: YouTube video URL
            output_path: Path where to save the downloaded video
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cmd = [
                "yt-dlp",
                "-f",
                "best",
                "-o",
                output_path,
                yt_url,
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error downloading video: {e.stderr.decode()}")
            return False
        except FileNotFoundError:
            print(
                "yt-dlp not found. Please install it using: pip install yt-dlp"
            )
            return False

    def clip_video(
        self,
        input_path: str,
        output_path: str,
        start_time: float,
        end_time: float,
    ) -> bool:
        """
        Clip a video using ffmpeg.
        
        Args:
            input_path: Path to the input video
            output_path: Path for the output clipped video
            start_time: Start time in seconds
            end_time: End time in seconds
            
        Returns:
            True if successful, False otherwise
        """
        try:
            duration = end_time - start_time
            cmd = [
                "ffmpeg",
                "-i",
                input_path,
                "-ss",
                str(start_time),
                "-t",
                str(duration),
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-y",
                output_path,
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error clipping video: {e.stderr.decode()}")
            return False
        except FileNotFoundError:
            print("ffmpeg not found. Please install it using: pip install ffmpeg-python")
            return False

    def upload_to_drive(
        self, file_path: str, folder_id: str, file_name: str
    ) -> Dict:
        """
        Upload a file to Google Drive.
        
        Args:
            file_path: Local path to the file to upload
            folder_id: Google Drive folder ID to upload to
            file_name: Name of the file in Google Drive
            
        Returns:
            Dictionary with upload result (file_id, name, etc.)
        """
        try:
            file_metadata = {
                "name": file_name,
                "parents": [folder_id],
            }
            media = MediaFileUpload(file_path, mimetype="video/mp4")
            file = (
                self.gdrive_service.files()
                .create(body=file_metadata, media_body=media, fields="id, name, webViewLink")
                .execute()
            )
            return {
                "success": True,
                "file_id": file.get("id"),
                "name": file.get("name"),
                "drive_link": file.get("webViewLink"),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def process_youtube_clip(
        self,
        yt_url: str,
        start_time: float,
        end_time: float,
        output_folder_id: str,
        clip_name: str = None,
    ) -> Dict:
        """
        Complete workflow: download, clip, and upload to Google Drive.
        
        Args:
            yt_url: YouTube video URL
            start_time: Start time in seconds (or MM:SS, HH:MM:SS format)
            end_time: End time in seconds (or MM:SS, HH:MM:SS format)
            output_folder_id: Google Drive folder ID to upload to
            clip_name: Custom name for the clipped video (optional)
            
        Returns:
            Dictionary with operation result
        """
        # Parse timestamps
        start_sec = self._parse_timestamp(start_time)
        end_sec = self._parse_timestamp(end_time)

        if start_sec >= end_sec:
            return {
                "success": False,
                "error": "Start time must be before end time",
            }

        temp_video_path = None
        try:
            # Step 1: Download the video
            temp_video_path = os.path.join(self.temp_dir, "yt_temp_video.mp4")
            print(f"Downloading video from {yt_url}...")
            if not self.download_video(yt_url, temp_video_path):
                return {
                    "success": False,
                    "error": "Failed to download video",
                }

            # Step 2: Clip the video
            clipped_video_path = os.path.join(self.temp_dir, "clipped_video.mp4")
            print(f"Clipping video from {start_sec}s to {end_sec}s...")
            if not self.clip_video(temp_video_path, clipped_video_path, start_sec, end_sec):
                return {
                    "success": False,
                    "error": "Failed to clip video",
                }

            # Step 3: Upload to Google Drive
            if not clip_name:
                duration_sec = int(end_sec - start_sec)
                clip_name = f"clip_{start_sec:.0f}s-{end_sec:.0f}s_{duration_sec}s.mp4"

            print(f"Uploading to Google Drive folder {output_folder_id}...")
            upload_result = self.upload_to_drive(
                clipped_video_path, output_folder_id, clip_name
            )

            if upload_result["success"]:
                return {
                    "success": True,
                    "file_id": upload_result["file_id"],
                    "file_name": upload_result["name"],
                    "drive_link": upload_result["drive_link"],
                    "clip_info": {
                        "youtube_url": yt_url,
                        "start_time": start_sec,
                        "end_time": end_sec,
                        "duration": end_sec - start_sec,
                    },
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to upload to Google Drive: {upload_result.get('error', 'Unknown error')}",
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
        finally:
            # Cleanup temporary files
            if temp_video_path and os.path.exists(temp_video_path):
                try:
                    os.remove(temp_video_path)
                except:
                    pass

    def process_batch_clips(
        self,
        clips_data: List[Dict],
        output_folder_id: str,
    ) -> Dict:
        """
        Process multiple clips from various YouTube videos.
        
        Args:
            clips_data: List of clip specifications
                Each dict should have:
                {
                    "url": "YouTube URL",
                    "start_time": start_time (seconds or MM:SS or HH:MM:SS),
                    "end_time": end_time (seconds or MM:SS or HH:MM:SS),
                    "name": "optional clip name"
                }
            output_folder_id: Google Drive folder ID to upload to
            
        Returns:
            Dictionary with batch processing results
        """
        results = {
            "total": len(clips_data),
            "successful": 0,
            "failed": 0,
            "clips": [],
        }

        for i, clip_spec in enumerate(clips_data, 1):
            print(f"\nProcessing clip {i}/{len(clips_data)}...")
            result = self.process_youtube_clip(
                yt_url=clip_spec["url"],
                start_time=clip_spec["start_time"],
                end_time=clip_spec["end_time"],
                output_folder_id=output_folder_id,
                clip_name=clip_spec.get("name"),
            )

            results["clips"].append(result)
            if result["success"]:
                results["successful"] += 1
            else:
                results["failed"] += 1

        return results
