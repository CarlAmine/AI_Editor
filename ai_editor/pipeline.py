import os
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google.oauth2 import service_account

from .analyzer import analyze_video_content_with_results
from .editor import create_and_render_video
from .overlay_planner import generate_overlay_plan

load_dotenv()

# Configuration from .env
shotstack_key = os.getenv("SHOTSTACK_KEY")
deepseek_key = os.getenv("DEEPSEEK_KEY")
gdrive_creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

# These are now retrieved to be passed as arguments later
env_folder_id = os.getenv("VIDEO_FOLDER")
env_sound_url = os.getenv("MUSIC_URL")


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
    """Authenticates using the Service Account JSON file."""
    creds = service_account.Credentials.from_service_account_file(
        gdrive_creds_path,
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    return build("drive", "v3", credentials=creds)


def get_drive_assets(service, folder_id):
    """Lists video files from the shared Google Drive folder."""
    query = f"'{folder_id}' in parents and trashed = false"
    results = service.files().list(q=query, fields="files(id, name, mimeType)").execute()
    
    links = []
    for f in results.get("files", []):
        if "video" in f["mimeType"]:
            # Shotstack needs a direct download link
            direct_link = f"https://drive.google.com/uc?export=download&id={f['id']}"
            links.append(direct_link)
    return links


def Assemble_Pipeline(file_path, prompt, folder_id, music_url):
    print("\n--- Step 1: Analyzing Video Content ---")
    summary, analysis_results = analyze_video_content_with_results(file_path)

    # Write analyzer outputs to disk so you can inspect them.
    try:
        with open("analysis_summary_debug.txt", "w", encoding="utf-8") as f:
            f.write(summary)
        with open("analysis_debug.json", "w", encoding="utf-8") as f:
            import json as _json
            _json.dump(analysis_results, f, ensure_ascii=False, indent=2)
        print(" Saved analyzer debug files: analysis_summary_debug.txt, analysis_debug.json")
    except Exception as e:
        print(f" Failed to write analyzer debug files: {e}")
    
    print("\n--- Step 2: Generating Requirements Report ---")
    report = generate_video_requirements_report(summary, [prompt], deepseek_key)
    print(report)

    print("\n--- Step 3: Generating Overlay Plan ---")
    overlay_plan = None
    try:
        overlay_plan = generate_overlay_plan(
            analysis_results=analysis_results,
            user_prompt=prompt,
            analysis_summary=summary,
        )
        if overlay_plan:
            print(f" Generated {len(overlay_plan)} overlay captions from analysis.")
        else:
            print(
                " No overlay captions generated; will fall back to simple prompt-based overlay text."
            )
    except Exception as e:
        print(f" Overlay planning failed, falling back to simple prompt text: {e}")
    
    print("\n--- Step 4: Gathering Assets from Google Drive ---")
    try:
        service = get_drive_service()
        # Uses folder_id passed via argument
        video_assets = get_drive_assets(service, folder_id)
        print(f" Found {len(video_assets)} videos in Drive.")
    except Exception as e:
        return {"success": False, "error": f"Drive API Error: {str(e)}"}

    if not video_assets:
        return {"success": False, "error": "No videos found in the specified GDrive folder."}

    print("\n--- Step 5: Rendering Video ---")
    # Uses music_url passed via argument
    result = create_and_render_video(
        api_key=shotstack_key,
        video_urls=video_assets,
        project_title="Pipeline Automated Edit",
        overlay_text=[prompt[:30]],  # Fallback overlay text
        soundtrack_url=music_url,
        resolution="1080x1920",
        wait_for_render=True,
        overlay_plan=overlay_plan,
    )
    return result


def main():
    print("========================================")
    print("Initializing the Editing Pipeline")
    print("========================================\n")
    
    video_input = input("Enter local Video Path: ").strip().replace('"', "")
    user_prompt = input("Describe your editing requirements: ").strip()

    try:
        # Pass the .env variables into the function call here
        pipeline_result = Assemble_Pipeline(
            file_path=video_input,
            prompt=user_prompt,
            folder_id=env_folder_id,
            music_url=env_sound_url,
        )
        
        if isinstance(pipeline_result, dict) and pipeline_result.get("success"):
            print(f"\nSUCCESS! Video URL: {pipeline_result.get('url')}")
        else:
            error_msg = pipeline_result.get("error") if isinstance(pipeline_result, dict) else pipeline_result
            print(f"\nPipeline failed: {error_msg}")
            
    except Exception as e:
        print(f"\nCritical Pipeline Error: {str(e)}")


if __name__ == "__main__":
    main()

