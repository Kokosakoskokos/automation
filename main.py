import os
import json
import shutil
import subprocess
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import FastAPI, UploadFile, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from pydantic import BaseModel

# ======================
# CONFIGURATION
# ======================
app = FastAPI(title="Podcast Shorts Automation")
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Load environment variables
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")
SCOPES = ["https://www.googleapis.com/auth/drive"]
YT_API_KEYS = [
    os.getenv("YT_API_KEY_1"),
    os.getenv("YT_API_KEY_2"),
    os.getenv("YT_API_KEY_3"),
    os.getenv("YT_API_KEY_4"),
    os.getenv("YT_API_KEY_5")
]

# Initialize Google services
gdrive_creds = service_account.Credentials.from_service_account_info(
    json.loads(os.getenv("GDRIVE_KEY")), 
    scopes=SCOPES
)
drive_service = build("drive", "v3", credentials=gdrive_creds)

# ======================
# CORE FUNCTIONS
# ======================
def upload_to_drive(file_path: str, folder_id: str, target_name: str) -> str:
    """Uploads file to Google Drive and returns file ID"""
    file_metadata = {
        "name": target_name,
        "parents": [folder_id]
    }
    media = MediaFileUpload(file_path, resumable=True)
    file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id"
    ).execute()
    return file.get("id")

def delete_old_files(folder_id: str, days: int = 3) -> int:
    """Deletes files older than X days, returns count deleted"""
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    query = f"'{folder_id}' in parents and modifiedTime < '{cutoff}'"
    files = drive_service.files().list(
        q=query,
        fields="files(id,name)"
    ).execute().get("files", [])
    
    for file in files:
        drive_service.files().delete(fileId=file["id"]).execute()
    
    return len(files)

def download_podcast(url: str, output_dir: str = "/tmp") -> str:
    """Downloads podcast using yt-dlp, returns file path"""
    output_path = f"{output_dir}/podcast_{datetime.now().strftime('%Y%m%d_%H%M%S')}.%(ext)s"
    cmd = [
        "yt-dlp",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "-o", output_path,
        "--no-playlist",
        url
    ]
    subprocess.run(cmd, check=True)
    
    # Find the actual downloaded file
    base_path = output_path.replace(".%(ext)s", "")
    for ext in [".mp4", ".mkv", ".webm"]:
        if os.path.exists(f"{base_path}{ext}"):
            return f"{base_path}{ext}"
    raise FileNotFoundError("Downloaded file not found")

def generate_clip(
    input_path: str,
    output_path: str,
    start_time: str = "00:00:00",
    duration: str = "00:00:60",
    subtitles: bool = True
) -> str:
    """Generates vertical clip with optional subtitles"""
    # Generate subtitles if requested
    srt_path = ""
    if subtitles:
        srt_path = input_path.replace(".mp4", ".srt")
        subprocess.run([
            "whisper",
            input_path,
            "--model", "small",
            "--output_dir", os.path.dirname(input_path),
            "--output_format", "srt"
        ], check=True)
    
    # Build FFmpeg command
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-ss", start_time,
        "-t", duration,
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "128k",
        output_path
    ]
    
    # Add subtitles if available
    if subtitles and os.path.exists(srt_path):
        cmd[6:6] = ["-vf", f"subtitles='{srt_path}':force_style='Fontsize=24,PrimaryColour=&HFFFFFF&'"]
    
    subprocess.run(cmd, check=True)
    return output_path

def upload_to_youtube(
    file_path: str,
    title: str,
    description: str,
    tags: List[str],
    privacy_status: str = "private"
) -> str:
    """Uploads video to YouTube using random API key, returns video ID"""
    youtube = build("youtube", "v3", developerKey=random.choice(YT_API_KEYS))
    
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": "22"  # Entertainment
            },
            "status": {
                "privacyStatus": privacy_status
            }
        },
        media_body=MediaFileUpload(file_path)
    )
    response = request.execute()
    return response.get("id")

# ======================
# API ENDPOINTS
# ======================
class ProcessRequest(BaseModel):
    url: str
    start_time: str = "00:00:00"
    duration: str = "00:00:60"
    title: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = []
    make_public: bool = False

@app.post("/api/process")
async def process_podcast(request: ProcessRequest):
    try:
        # 1. Download podcast
        podcast_path = download_podcast(request.url)
        
        # 2. Generate clip
        clip_path = podcast_path.replace(".mp4", "_clip.mp4")
        generate_clip(
            podcast_path,
            clip_path,
            start_time=request.start_time,
            duration=request.duration
        )
        
        # 3. Upload to YouTube
        base_title = request.title or f"Podcast Clip {datetime.now().strftime('%Y-%m-%d')}"
        video_id = upload_to_youtube(
            clip_path,
            title=base_title,
            description=request.description or f"Clip from {request.url}",
            tags=request.tags or ["podcast", "shorts"],
            privacy_status="public" if request.make_public else "private"
        )
        
        # 4. Archive to Drive
        drive_id = upload_to_drive(
            clip_path,
            GDRIVE_FOLDER_ID,
            f"clip_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        )
        
        # 5. Cleanup
        os.remove(podcast_path)
        os.remove(clip_path)
        if os.path.exists(podcast_path.replace(".mp4", ".srt")):
            os.remove(podcast_path.replace(".mp4", ".srt"))
        
        return {
            "status": "success",
            "youtube_id": video_id,
            "drive_id": drive_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/cleanup")
async def cleanup_files(days: int = 3):
    try:
        deleted_count = delete_old_files(GDRIVE_FOLDER_ID, days)
        return {"status": "success", "deleted": deleted_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/system-info")
async def system_info():
    return {
        "storage": shutil.disk_usage("/"),
        "load": os.getloadavg(),
        "date": datetime.now().isoformat()
    }

# ======================
# FRONTEND SERVING
# ======================
@app.get("/")
async def serve_frontend():
    return FileResponse("frontend/index.html")

# ======================
# BACKGROUND TASKS
# ======================
@app.on_event("startup")
async def startup_tasks():
    # Ensure temp directory exists
    os.makedirs("/tmp/podcast_automation", exist_ok=True)
    
    # Initial cleanup
    delete_old_files(GDRIVE_FOLDER_ID)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
