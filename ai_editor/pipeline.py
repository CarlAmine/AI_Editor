import os
import shutil
from pathlib import Path
from dotenv import load_dotenv

from .analyzer import analyze_video_content_with_results
from .editor import create_and_render_video
from .overlay_planner import generate_overlay_plan
from .downloader import download_video, download_and_clip, cleanup_directory, VideoDownloadError

load_dotenv()

# Configuration from .env
shotstack_key = os.getenv("SHOTSTACK_KEY")
deepseek_key = os.getenv("DEEPSEEK_KEY")


def generate_video_requirements_report(analyzer_output, user_instructions, api_key=None):
    """
    Lightweight placeholder for the previous LLM-based requirements generator.
    Keeps the pipeline functional even if no external LLM is configured.
    """
    joined_instructions = "\n".join(user_instructions) if user_instructions else ""
    return (
        "VIDEO ANALYSIS (AUTO-GENERATED SUMMARY)\n"
        "---------------------------------------\n"
        f"{analyzer_output}\n\n"
        "USER REQUIREMENTS\n"
        "-----------------\n"
        f"{joined_instructions}"
    )


def get_drive_service():
    """Deprecated: Google Drive integration has been removed."""
    raise NotImplementedError("Google Drive integration has been replaced with local file-based workflow.")


def get_drive_assets(service, folder_id):
    """Deprecated: Google Drive integration has been removed."""
    raise NotImplementedError("Google Drive integration has been replaced with local file-based workflow.")


def Assemble_Pipeline(
    primary_url: str,
    sources: list = None,
    prompt: str = "",
    music_mode: str = "original",
    custom_music_url: str = None,
    requirements_state: dict = None,
    job_id: str = None,
    gdrive_folder_id: str = None,
) -> dict:
    """
    New URL-based pipeline that downloads videos, analyzes, and renders.
    
    Args:
        primary_url: YouTube/TikTok URL for analysis
        sources: List of dicts with {label, url, segments}
        prompt: User editing prompt
        music_mode: "original" or "custom"
        custom_music_url: URL to custom audio (if music_mode=="custom")
        requirements_state: UI state (tone, pacing, aspect_ratio, etc.)
        job_id: Unique ID for this job (used for cleanup)
    
    Returns:
        Dict with success, url, error (if failed)
    """
    if requirements_state is None:
        requirements_state = {}
    
    # Create a working directory for this job
    import uuid
    job_id = job_id or str(uuid.uuid4())[:8]
    work_dir = os.path.join("./tmp/videos", job_id)
    os.makedirs(work_dir, exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"Starting Pipeline (Job: {job_id})")
    print(f"{'='*60}")
    
    try:
        # Extract UI state
        user_tone = requirements_state.get("tone")
        user_pacing = requirements_state.get("pacing")
        aspect_ratio = requirements_state.get("aspect_ratio", "9:16")
        orientation = requirements_state.get("orientation", "vertical")
        call_to_action = requirements_state.get("call_to_action")
        
        # --- Step 1: Download and analyze primary video ---
        print("\n[Step 1] Downloading primary video for analysis...")
        try:
            primary_video_path = download_video(primary_url, work_dir, "primary.mp4")
        except VideoDownloadError as e:
            return {"success": False, "error": f"Failed to download primary video: {str(e)}"}
        
        # --- Step 2: Analyze the video ---
        print("\n[Step 2] Analyzing video content...")
        summary, analysis_results = analyze_video_content_with_results(primary_video_path)
        
        # Save debug files
        try:
            with open(os.path.join(work_dir, "analysis_summary.txt"), "w", encoding="utf-8") as f:
                f.write(summary)
            with open(os.path.join(work_dir, "analysis.json"), "w", encoding="utf-8") as f:
                import json as _json
                _json.dump(analysis_results, f, ensure_ascii=False, indent=2)
            print(f"✓ Saved analysis to {work_dir}/")
        except Exception as e:
            print(f"⚠ Could not save analysis files: {e}")
        
        # --- Step 3: Generate requirements report ---
        print("\n[Step 3] Generating requirements report...")
        report = generate_video_requirements_report(summary, [prompt], deepseek_key)
        print(report[:200] + "...")
        
        # --- Step 4: Generate overlay plan ---
        print("\n[Step 4] Generating overlay plan...")
        overlay_plan = None
        try:
            overlay_plan = generate_overlay_plan(
                analysis_results=analysis_results,
                user_prompt=prompt,
                analysis_summary=summary,
                tone=user_tone,
                pacing=user_pacing,
            )
            if overlay_plan:
                print(f"✓ Generated {len(overlay_plan)} overlay captions")
            else:
                print("- No overlay plan generated (OK)")
        except Exception as e:
            print(f"⚠ Overlay planning failed (will use fallback): {e}")
        
        # --- Step 5: Acquire source videos (either provided URLs or Google Drive) ---
        print("\n[Step 5] Acquiring source videos...")

        clips = []
        video_urls = []

        # If a Google Drive folder id was provided, try to fetch assets
        if gdrive_folder_id:
            print(f"[Step 5a] Downloading assets from Google Drive folder: {gdrive_folder_id}")
            try:
                # Lazy import for optional dependency
                from google.oauth2 import service_account
                from googleapiclient.discovery import build
                from googleapiclient.http import MediaIoBaseDownload
                import io

                sa_path = os.path.join(os.getcwd(), "service-account.json")
                if not os.path.exists(sa_path):
                    return {"success": False, "error": "Google service-account.json not found in project root."}

                scopes = ["https://www.googleapis.com/auth/drive.readonly"]
                creds = service_account.Credentials.from_service_account_file(sa_path, scopes=scopes)
                drive = build('drive', 'v3', credentials=creds)

                # List files in folder (only basic video mimeType filter)
                q = f"'{gdrive_folder_id}' in parents and (mimeType contains 'video' or mimeType contains 'video/')"
                resp = drive.files().list(q=q, fields="files(id,name,mimeType)").execute()
                files = resp.get('files', [])

                if not files:
                    return {"success": False, "error": "No video files found in the provided Google Drive folder."}

                for idx, f in enumerate(files, start=1):
                    file_id = f['id']
                    filename = f.get('name') or f"drive_video_{idx}.mp4"
                    out_path = os.path.join(work_dir, f"drive_{idx}_{filename}")
                    fh = io.FileIO(out_path, 'wb')
                    request = drive.files().get_media(fileId=file_id)
                    downloader = MediaIoBaseDownload(fh, request)
                    done = False
                    while not done:
                        status, done = downloader.next_chunk()
                    fh.close()
                    clips.append({"label": idx, "segment": 0, "path": out_path})
                    video_urls.append(out_path)

                print(f"✓ Downloaded {len(clips)} files from Drive")

            except FileNotFoundError:
                return {"success": False, "error": "Google Drive libraries not installed or service account file missing."}
            except Exception as e:
                return {"success": False, "error": f"Failed to download from Google Drive: {e}"}

        else:
            # Default: expect `sources` to be provided (list of dicts)
            print("[Step 5b] Downloading and clipping source videos from provided URLs...")
            clip_result = download_and_clip(sources or [], work_dir)

            if not clip_result["success"]:
                return {"success": False, "error": f"Clipping failed: {clip_result.get('error')}"}

            clips = clip_result.get("clips", [])
            print(f"✓ Created {len(clips)} clips")

            # Extract video URLs in the correct order
            video_urls = [clip["path"] for clip in clips]
        
        # --- Step 6: Handle music ---
        print("\n[Step 6] Handling audio/music...")
        music_url = None
        
        if music_mode == "custom" and custom_music_url:
            print(f"- Using custom music from: {custom_music_url}")
            # Download and extract audio from custom URL
            try:
                from .downloader import extract_audio
                custom_video = download_video(custom_music_url, work_dir, "custom_music_source.mp4")
                music_url = extract_audio(custom_video, work_dir, "custom_music.mp3")
                print(f"✓ Extracted custom music: {music_url}")
            except Exception as e:
                print(f"⚠ Failed to extract custom music, will use original audio: {e}")
                music_url = None
        elif music_mode == "original":
            print("- Preserving original audio from clips")
            music_url = None
        
        # --- Step 7: Determine resolution ---
        print("\n[Step 7] Determining output resolution...")
        if aspect_ratio == "16:9" or orientation == "horizontal":
            resolution_str = "1920x1080"
        elif aspect_ratio == "1:1" or orientation == "square":
            resolution_str = "1080x1080"
        else:
            resolution_str = "1080x1920"  # 9:16 vertical
        print(f"✓ Output resolution: {resolution_str}")
        
        # --- Step 8: Build overlay plan with CTA---
        print("\n[Step 8] Building final overlay plan...")
        final_overlay_plan = overlay_plan[:] if overlay_plan else []
        if call_to_action:
            last_ts = max((float(o.get("timestamp", 0)) for o in final_overlay_plan), default=0)
            final_overlay_plan.append({
                "timestamp": last_ts + 2.0,
                "text": call_to_action,
                "position": "center"
            })
            print(f"✓ Added CTA to overlay")
        
        # --- Step 9: Render with Shotstack ---
        print("\n[Step 9] Rendering video with Shotstack...")
        render_result = create_and_render_video(
            api_key=shotstack_key,
            video_urls=video_urls,
            project_title=f"Auto-Edit ({job_id})",
            overlay_text=[prompt[:50]],
            soundtrack_url=music_url,
            music_mode=music_mode,
            resolution=resolution_str,
            wait_for_render=True,
            overlay_plan=final_overlay_plan if final_overlay_plan else None,
        )
        
        if not render_result.get("success"):
            return {"success": False, "error": f"Render failed: {render_result.get('error')}"}
        
        print(f"\n{'='*60}")
        print(f"✓ SUCCESS! Video ready at:")
        print(f"  {render_result.get('url')}")
        print(f"{'='*60}")
        
        return render_result
    
    except Exception as e:
        print(f"\n✗ PIPELINE ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": f"Pipeline error: {str(e)}"}
    
    finally:
        # Always cleanup the working directory
        print(f"\n[Cleanup] Removing temporary files from {work_dir}...")
        cleanup_directory(work_dir)


def main():
    """Legacy CLI for testing (kept for backwards compatibility)."""
    print("========================================")
    print("Initializing the Editing Pipeline")
    print("========================================\n")
    
    print("NOTE: This CLI endpoint is deprecated.")
    print("Please use the API endpoint /process-video-url instead.")


if __name__ == "__main__":
    main()
