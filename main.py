import os
import re
import traceback
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import yt_dlp

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

RAW_KEYS = os.getenv("API_KEYS", "")
VALID_API_KEYS = set(k.strip() for k in RAW_KEYS.split(",") if k.strip())

def verify_key(x_api_key: str = Header(...)):
    if VALID_API_KEYS and x_api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return x_api_key


class MediaRequest(BaseModel):
    url: str
    quality: Optional[str] = "best"


QUALITY_MAP = {
    "best":  "bestvideo+bestaudio/best",
    "720":   "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480":   "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "360":   "bestvideo[height<=360]+bestaudio/best[height<=360]",
    "audio": "bestaudio",
}


def extract_media_info(url: str, quality: str):
    ydl_opts = {
        "format": QUALITY_MAP.get(quality, QUALITY_MAP["best"]),
        "quiet": True,
        "noplaylist": True,
        "http_headers": {"User-Agent": "Mozilla/5.0"},
    }

    if os.path.exists("cookies.txt"):
        ydl_opts["cookiefile"] = "cookies.txt"

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    formats = []
    for f in info.get("formats", []):
        if f.get("url"):
            formats.append({
                "quality": str(f.get("height")),
                "url": f.get("url")
            })

    formats = formats[::-1][:10]

    return {
        "title": info.get("title"),
        "thumbnail": info.get("thumbnail"),
        "download_url": formats[0]["url"] if formats else None,
        "formats": formats
    }


def detect_platform(url: str):
    if re.search(r"(youtube\.com|youtu\.be)", url):
        return "youtube"
    if "instagram.com" in url:
        return "instagram"
    if "facebook.com" in url:
        return "facebook"
    return None


@app.get("/")
def home():
    return {"status": "running"}


@app.post("/api/download")
def download(req: MediaRequest, x_api_key: str = Header(...)):
    verify_key(x_api_key)

    platform = detect_platform(req.url)
    if not platform:
        raise HTTPException(400, "Unsupported URL")

    try:
        data = extract_media_info(req.url, req.quality)
        return {"success": True, "platform": platform, "data": data}

    except Exception:
        print(traceback.format_exc())
        raise HTTPException(500, "Server Error")
