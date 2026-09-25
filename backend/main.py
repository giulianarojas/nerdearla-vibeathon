from pathlib import Path
from fastapi import FastAPI
from backend.session_manager import SessionManager
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import WebSocket
from fastapi import HTTPException
from pydantic import BaseModel


BASE_DIR = Path(__file__).resolve().parent.parent
AUDIO_DIR = BASE_DIR / "audio"

app = FastAPI(
    title="Nerdearla Live Captions",
    description="Open-source real-time conference transcription system",
    version="0.1.0",
)

session_manager = SessionManager(max_sessions=10)
websocket_connections = {}

class StartSessionRequest(BaseModel):
    audio: str

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

@app.post("/api/sessions/{session_id}/start")
async def start_session(
    session_id: str,
    request: StartSessionRequest,
):
    session = session_manager.get_session(
        session_id
    )

    if not session:

        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )

    audio_path = (
        AUDIO_DIR / request.audio
    ).resolve()

    audio_directory = AUDIO_DIR.resolve()

    # Seguridad: el archivo debe permanecer
    # dentro de la carpeta audio/
    if audio_directory not in audio_path.parents:

        raise HTTPException(
            status_code=400,
            detail="Invalid audio path",
        )

    if not audio_path.exists():

        raise HTTPException(
            status_code=404,
            detail="Audio not found",
        )

    try:

        await session_manager.start_session(
            session_id,
            audio_path,
            websocket_connections[session_id],
        )

    except RuntimeError as error:

        raise HTTPException(
            status_code=409,
            detail=str(error),
        )

    return {
        "session_id": session_id,
        "audio": request.audio,
        "status": "running",
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

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str
):
    await websocket.accept()

    session = session_manager.get_session(session_id)

    if not session:
        await websocket.send_json({
            "type": "error",
            "message": "Sala no encontrada"
        })

        await websocket.close()

        return
    websocket_connections[session_id] = websocket

    try:
        while True:
            message = await websocket.receive_json()

            print(
                f"[{session_id}] "
                f"Mensaje recibido:",
                message
            )

    except Exception as error:
        print(
            f"[{session_id}] "
            f"WebSocket cerrado:",
            error
        )

    finally: 
        websocket_connections.pop(session_id, None)