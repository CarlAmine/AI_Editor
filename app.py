from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
from Pipeline import Assemble_Pipeline

app = FastAPI()

# Enable CORS so Lovable can talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/process-video")
async def process_video(
    prompt: str = Form(...), 
    video: UploadFile = File(...)
):
    # 1. Save the uploaded video locally for Analyzer.py to read
    temp_path = f"temp_{video.filename}"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(video.file, buffer)
    
    try:
        # 2. Run your existing pipeline logic
        # Assemble_Pipeline uses Analyzer, Chatbot, and Editor internally
        result = Assemble_Pipeline(temp_path, prompt)
        return result
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path) # Cleanup