from pathlib import Path
from fastapi import FastAPI
from backend.session_manager import SessionManager
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(
    title="Nerdearla Live Captions",
    description="Open-source real-time conference transcription system",
    version="0.1.0",
)

session_manager = SessionManager(max_sessions=10)

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

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "frontend"),
    name="static")

@app.get("/")
async def home():
    return FileResponse(BASE_DIR / "frontend" / "index.html")


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "nerdearla-live-captions",
    }