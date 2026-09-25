from pathlib import Path
from fastapi import FastAPI
from backend.session_manager import SessionManager
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

BASE_DIR = Path(__file__).resolve().parent.parent
AUDIO_DIR = BASE_DIR / "audio"

app = FastAPI(
    title="Nerdearla Live Captions",
    description="Open-source real-time conference transcription system",
    version="0.1.0",
)

session_manager = SessionManager(max_sessions=10)

# --- Archivos estáticos ---
app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "frontend"),
    name="static")

app.mount(
    "/audio",
    StaticFiles(directory=AUDIO_DIR),
    name="audio"
)

# --- Endpoints ---

@app.post("/api/sessions")
async def create_session():
    try:
        session_id = session_manager.create_session()

        return {
            "session_id": session_id
        }

    except RuntimeError as error:
        return {
            "error": str(error)
        }

@app.get("/")
async def home():
    return FileResponse(BASE_DIR / "frontend" / "index.html")


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "nerdearla-live-captions",
    }

@app.get("/api/audios")
async def list_audio():
    audio_files = [
        file.name
        for file in AUDIO_DIR.iterdir()
        if file.suffix.lower() in [".mp3", ".wav"]
    ]

    return {
        "audio": sorted(audio_files)
    }

