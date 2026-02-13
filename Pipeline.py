from Analyzer import *
from ChatbotInterface import *
from Editor import *
import os
from dotenv import load_dotenv
from googleapiclient.discovery import build
from google.oauth2 import service_account

load_dotenv()

# Configuration from .env
shotstack_key = os.getenv("SHOTSTACK_KEY")
deepseek_key = os.getenv("DEEPSEEK_KEY")
folder_id = os.getenv("VIDEO_FOLDER") 
sound = os.getenv("MUSIC_URL")
gdrive_creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") 

def get_drive_service():
    """Authenticates using the Service Account JSON file."""
    creds = service_account.Credentials.from_service_account_file(
        gdrive_creds_path, 
        scopes=['https://www.googleapis.com/auth/drive.readonly']
    )
    return build('drive', 'v3', credentials=creds)

def get_drive_assets(service, folder_id):
    """Lists video files from the shared Google Drive folder."""
    query = f"'{folder_id}' in parents and trashed = false"
    results = service.files().list(q=query, fields="files(id, name, mimeType)").execute()
    
    links = []
    for f in results.get('files', []):
        if 'video' in f['mimeType']:
            # Shotstack needs a direct download link
            direct_link = f"https://drive.google.com/uc?export=download&id={f['id']}"
            links.append(direct_link)
    return links

def Assemble_Pipeline(file_path, prompt):
    print("\n--- Step 1: Analyzing Video Content ---")
    summary = analyze_video_content(file_path) # Runs local analysis
    
    print("\n--- Step 2: Generating Requirements Report ---")
    # Generates structured brief via DeepSeek
    report = generate_video_requirements_report(summary, [prompt], deepseek_key) 
    print(report)

    print("\n--- Step 3: Gathering Assets from Google Drive ---")
    try:
        service = get_drive_service()
        video_assets = get_drive_assets(service, folder_id)
        print(f" Found {len(video_assets)} videos in Drive.")
    except Exception as e:
        return {"success": False, "error": f"Drive API Error: {str(e)}"}

    if not video_assets:
        return {"success": False, "error": "No videos found in the specified GDrive folder."}

    print("\n--- Step 4: Rendering Video ---")
    # Assembles assets using Shotstack SDK
    result = create_and_render_video(
        api_key=shotstack_key,
        video_urls=video_assets,
        project_title="Pipeline Automated Edit",
        overlay_text=[prompt[:30]], 
        soundtrack_url=sound,
        wait_for_render=True
    )
    return result

def main():
    print("========================================")
    print("Initializing the Editing Pipeline")
    print("========================================\n")
    
    # Analyzer handles local files; input clean-up for Windows paths
    video_input = input("Enter local Video Path: ").strip().replace('"', '')
    user_prompt = input("Describe your editing requirements: ").strip()

    try:
        pipeline_result = Assemble_Pipeline(video_input, user_prompt)
        
        # Fixed logic to prevent 'str' object has no attribute 'get' error
        if isinstance(pipeline_result, dict) and pipeline_result.get("success"):
            print(f"\nSUCCESS! Video URL: {pipeline_result.get('url')}")
        else:
            error_msg = pipeline_result.get("error") if isinstance(pipeline_result, dict) else pipeline_result
            print(f"\nPipeline failed: {error_msg}")
            
    except Exception as e:
        print(f"\nCritical Pipeline Error: {str(e)}")

if __name__ == "__main__":
    main()